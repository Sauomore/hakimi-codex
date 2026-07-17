"""Random number generator with multiple distribution options."""

import random
import secrets
from typing import List, Optional, Sequence, TypeVar

T = TypeVar("T")


class RandomGenerator:
    """A versatile random number generator with multiple distribution options."""

    @staticmethod
    def seed(value: Optional[int] = None) -> None:
        """Seed the shared random number generator.

        Args:
            value: Seed value. If None, seeds from system entropy.
        """
        random.seed(value)

    @staticmethod
    def uniform(a: float = 0.0, b: float = 1.0) -> float:
        """Return a random float in [a, b)."""
        return random.uniform(a, b)

    @staticmethod
    def randint(a: int, b: int) -> int:
        """Return a random integer in [a, b] (inclusive)."""
        return random.randint(a, b)

    @staticmethod
    def choice(seq: Sequence[T]) -> T:
        """Return a random element from a non-empty sequence."""
        return random.choice(seq)

    @staticmethod
    def sample(population: Sequence[T], k: int) -> List[T]:
        """Return a k-length list of unique elements from the population."""
        return random.sample(population, k)

    @staticmethod
    def shuffle(seq: List[T]) -> None:
        """Shuffle the sequence in place."""
        random.shuffle(seq)

    @staticmethod
    def normal(mean: float = 0.0, std_dev: float = 1.0) -> float:
        """Return a random float from a normal (Gaussian) distribution."""
        return random.gauss(mean, std_dev)

    @staticmethod
    def triangular(low: float = 0.0, high: float = 1.0, mode: Optional[float] = None) -> float:
        """Return a random float from a triangular distribution."""
        return random.triangular(low, high, mode)

    @staticmethod
    def exponential(lambd: float = 1.0) -> float:
        """Return a random float from an exponential distribution.

        Args:
            lambd: Rate parameter (1 / mean).
        """
        return random.expovariate(lambd)

    @staticmethod
    def beta(alpha: float, beta_param: float) -> float:
        """Return a random float from a Beta distribution."""
        return random.betavariate(alpha, beta_param)

    @staticmethod
    def gamma(shape: float, scale: float = 1.0) -> float:
        """Return a random float from a Gamma distribution."""
        return random.gammavariate(shape, scale)

    @staticmethod
    def lognormal(mean: float = 0.0, std_dev: float = 1.0) -> float:
        """Return a random float from a log-normal distribution."""
        return random.lognormvariate(mean, std_dev)

    @staticmethod
    def vonmises(mu: float = 0.0, kappa: float = 1.0) -> float:
        """Return a random float from a von Mises distribution."""
        return random.vonmisesvariate(mu, kappa)

    @staticmethod
    def weibull(alpha: float, beta_param: float) -> float:
        """Return a random float from a Weibull distribution."""
        return random.weibullvariate(alpha, beta_param)

    @staticmethod
    def secure_random_int(a: int, b: int) -> int:
        """Return a cryptographically secure random integer in [a, b]."""
        return secrets.randbelow(b - a + 1) + a

    @staticmethod
    def secure_random_bits(k: int) -> int:
        """Return a cryptographically secure integer with k random bits."""
        return secrets.randbits(k)

    @staticmethod
    def secure_choice(seq: Sequence[T]) -> T:
        """Return a cryptographically secure random element from a sequence."""
        if not seq:
            raise IndexError("Cannot choose from an empty sequence")
        return seq[secrets.randbelow(len(seq))]

    @staticmethod
    def secure_token_hex(nbytes: int = 16) -> str:
        """Return a secure random hexadecimal token."""
        return secrets.token_hex(nbytes)

    @staticmethod
    def secure_token_urlsafe(nbytes: int = 16) -> str:
        """Return a secure URL-safe random token."""
        return secrets.token_urlsafe(nbytes)


if __name__ == "__main__":
    RandomGenerator.seed(42)

    print("Uniform [0, 1):", RandomGenerator.uniform())
    print("Integer [1, 100]:", RandomGenerator.randint(1, 100))
    print("Normal(0, 1):", RandomGenerator.normal())
    print("Triangular(0, 10, 5):", RandomGenerator.triangular(0, 10, 5))
    print("Exponential(1.5):", RandomGenerator.exponential(1.5))
    print("Choice from ['a', 'b', 'c']:", RandomGenerator.choice(["a", "b", "c"]))
    print("Sample 3 from range(10):", RandomGenerator.sample(range(10), 3))

    print("Secure int [1, 100]:", RandomGenerator.secure_random_int(1, 100))
    print("Secure hex token:", RandomGenerator.secure_token_hex())
