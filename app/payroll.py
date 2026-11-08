"""Selected ordinary resident PAYG scales and adult Cleaning Services Award rates.

Not an STP, leave, SuperStream or award interpretation engine. See README safety notes.
Data: Taxation Administration (Withholding Schedules) Instrument 2026, Schedule 1;
Cleaning Services Award MA000022 effective 1 July 2026.
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

BASE_2026 = {1: 27.08, 2: 27.97, 3: 29.45}
RATES = {
    'full_time': {'ordinary':1,'early':1.15,'night':1.30,'saturday':1.50,'sunday':2,'public_holiday':2.50,'overtime_1':1.50,'overtime_2':2},
    'part_time': {'ordinary':1.15,'early':1.30,'night':1.30,'saturday':1.65,'sunday':2.15,'public_holiday':2.65,'overtime_1':1.50,'overtime_2':2},
    'casual': {'ordinary':1.25,'early':1.40,'night':1.55,'saturday':1.75,'sunday':2.25,'public_holiday':2.75,'overtime_1':1.75,'overtime_2':2.25},
}
SCALE1 = [(188,.15,.15),(371,.2084,11.0185),(515,.179,.1066),(932,.3227,74.1674),(2246,.32,71.6508),(3303,.39,228.8816),(float('inf'),.47,493.1893)]
SCALE2 = [(362,0,0),(538,.15,54.3462),(673,.25,108.2135),(721,.17,54.3473),(865,.179,60.8377),(1282,.3227,185.1935),(2596,.32,181.7319),(3653,.39,363.4627),(float('inf'),.47,655.7704)]

def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def aud_round(value):
    return int(Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def award_rate(base_rate, employment_type, category):
    if employment_type not in RATES or category not in RATES[employment_type]:
        raise ValueError('Unsupported employment type or category')
    return money(Decimal(str(base_rate)) * Decimal(str(RATES[employment_type][category])))

def payg_2026(gross, frequency='fortnightly', tax_free_threshold=True):
    """2026 Scale 1/2 general resident, no Medicare adjustment/offsets/HELP.
    Valid for taxable wages and withholding already agreed to be on these scales.
    """
    gross=Decimal(str(gross))
    if gross < 0: raise ValueError('Gross earnings cannot be negative')
    if frequency=='weekly': eq=gross
    elif frequency=='fortnightly': eq=gross / Decimal('2')
    elif frequency=='monthly':
        if int(gross*100) % 100 == 33: gross += Decimal('.01')
        eq=gross*Decimal('3')/Decimal('13')
    else: raise ValueError('Frequency must be weekly, fortnightly or monthly')
    x=Decimal(int(eq)) + Decimal('0.99')
    for threshold,a,b in SCALE2 if tax_free_threshold else SCALE1:
        if x < Decimal(str(threshold)):
            w=max(0,aud_round(Decimal(str(a))*x-Decimal(str(b))))
            if frequency=='fortnightly': return w*2
            if frequency=='monthly': return aud_round(Decimal(w)*Decimal(13)/Decimal(3))
            return w
    raise AssertionError('PAYG coefficient missing')
