"""RN-03: hasta 14:00 sin cargo; 14:00-18:00 medio día; después noche completa."""
from datetime import time
from decimal import Decimal, ROUND_HALF_UP


def late_checkout_charge(local_time: time, nightly_rate: Decimal) -> Decimal:
    if not isinstance(nightly_rate, Decimal) or not nightly_rate.is_finite() or nightly_rate <= 0:
        raise ValueError('Se requiere tarifa nocturna aceptada y válida.')
    if local_time <= time(14, 0):
        return Decimal('0.00')
    factor=Decimal('0.50') if local_time<=time(18,0) else Decimal('1.00')
    return (nightly_rate*factor).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
