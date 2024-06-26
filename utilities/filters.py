import torch
import math

from typing import Iterable, Tuple, Optional, Union

_sqrt2pi = math.sqrt(2*math.pi)

class Filter:
    @staticmethod
    def _fix_parameters(*parameters):
        parameters_fixed = [(parameter, ) if isinstance(parameter, float) else tuple(parameter) if parameter is not None else None for parameter in parameters]
        return tuple(parameters_fixed)
    @staticmethod
    def _fix_coordinates(dims:int, *coordinates:torch.Tensor) -> Tuple[torch.Tensor, ...]:
        if len(coordinates) != dims: raise ValueError('Amount of coordinates must equal the number of dimensions')

        size = coordinates[0].size()
        if dims != 1:
            if all(len(coord.size()) == 1 for coord in coordinates):
                coordinates = torch.meshgrid(*coordinates, indexing='ij')
            elif not all(coord.size() == size for coord in coordinates):
                raise ValueError(f'Coordinates must have the same size')
        return coordinates

    @property
    def dims(self):
        raise NotImplementedError

    def __call__(self, *coordinates) -> torch.Tensor:
        raise NotImplementedError

class Gaussian(Filter):
    _sigmas:Tuple[float, ...]
    _means: Tuple[float, ...]
    _limits:Optional[Tuple[Tuple[float, float], ...]]

    _normalization:float
    def _set_normalization(self):
        self._normalization = 1.0
        for sigma in self._sigmas:
            self._normalization *= 1.0 / (sigma * _sqrt2pi)

    _multipliers:Tuple[float, ...]
    def _set_multipliers(self):
        self._multipliers = tuple([-1.0 / (2. * sigma * sigma) for sigma in self._sigmas])

    @property
    def dims(self):
        return len(self._sigmas)

    def __init__(self, sigmas:Union[Iterable[float],float], means:Optional[Union[Iterable[float],float]]=None, limits:Optional[Union[Iterable[Tuple[float, float]], Tuple[float, float]]]=None):
        if isinstance(sigmas, float):   self._sigmas = (sigmas, )
        else:                           self._sigmas = tuple(sigmas)

        if means is None:               self._means = tuple([0 for _ in range(self.dims)])
        elif isinstance(means, float):  self._means = (means, )
        else:                           self._means = tuple(means)

        if limits is None:              self._limits = None
        elif isinstance(limits, tuple) and len(limits) == 2 and all(isinstance(item, float) for item in limits):
            limits:tuple[float, float]
            self._limits = (limits, )
        else:                           self._limits = tuple(limits)

        if len(self._sigmas) != self.dims or len(self._means) != self.dims or (self._limits is not None and len(self._limits) != self.dims):
            raise ValueError('sigmas, means and limits must have the same length')

        self._set_normalization()
        self._set_multipliers()

    def __call__(self, *coordinates:torch.Tensor) -> torch.Tensor:
        coordinates = self._fix_coordinates(self.dims, *coordinates)
        result = torch.ones(coordinates[0].size(), dtype=coordinates[0].dtype, device=coordinates[0].device) * self._normalization
        for multiplier, mean, coordinate in zip(self._multipliers, self._means, coordinates):
            result *= torch.exp(multiplier * (mean - coordinate)**2)
        return result

class Window(Filter):
    _positions0:Tuple[float, ...]
    _positions1:Tuple[float, ...]
    @property
    def dims(self):
        return len(self._positions0)

    def __init__(self, positions0:Union[Iterable[float],float]=None, positions1:Union[Iterable[float],float]=None, centers:Union[Iterable[float],float]=None, sizes:Union[Iterable[float],float]=None):
        positions0, positions1, centers, sizes = self._fix_parameters(positions0, positions1, centers, sizes)
        if positions0 is not None and positions1 is not None:
            self._positions0 = positions0
            self._positions1 = positions1
        elif positions0 is not None and sizes is not None:
            self._positions0 = positions0
            self._positions1 = tuple([position0 + size for position0, size in zip(positions0, sizes)])
        elif positions1 is not None and sizes is not None:
            self._positions1 = positions1
            self._positions0 = tuple([position1 - size for position1, size in zip(positions1, sizes)])
        elif centers is not None and sizes is not None:
            self._positions0 = tuple([center - size/2 for center, size in zip(centers, sizes)])
            self._positions1 = tuple([center + size/2 for center, size in zip(centers, sizes)])
        else: raise AttributeError

    def __call__(self, *coordinates:torch.Tensor):
        coordinates = self._fix_coordinates(self.dims, *coordinates)
        result = torch.ones(coordinates[0].size(), dtype=coordinates[0].dtype, device=coordinates[0].device)
        for position0, position1, coordinate in zip(self._positions0, self._positions1, coordinates):
            result *= (position0 <= coordinate) * (coordinate <= position1)
        return result