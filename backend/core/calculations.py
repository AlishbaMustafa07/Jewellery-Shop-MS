"""Business formulas (spec section 5). All inputs and outputs are Decimal.

Units: weights in grams (3 dp), gold rate in PKR per tola (1 tola = 11.664 g),
ratti kaat = purity in 96ths, money rounded to the nearest rupee.
"""
from decimal import ROUND_HALF_UP, Decimal

TOLA_GRAMS = Decimal("11.664")
PURE = Decimal("96")
ZERO = Decimal("0")

WEIGHT_Q = Decimal("0.001")
PASA_Q = Decimal("0.0001")


def D(value):
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q_weight(value):
    return D(value).quantize(WEIGHT_Q, rounding=ROUND_HALF_UP)


def q_pasa(value):
    return D(value).quantize(PASA_Q, rounding=ROUND_HALF_UP)


def q_money(value):
    """Round money to the nearest rupee (stored with .00)."""
    return D(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))


def gold_weight(gross, big_stone=0, pd_diamond=0, extra_less=0):
    """Gold Wt = Gross - Big Stone - Palladium/Diamond +/- Extra/Less gold."""
    return q_weight(D(gross) - D(big_stone) - D(pd_diamond) + D(extra_less))


def pasa_exact(gold_wt, ratti_kaat):
    return D(gold_wt) * D(ratti_kaat) / PURE


def pasa(gold_wt, ratti_kaat):
    """Pasa = Gold Wt x Ratti Kaat / 96 (pure-gold equivalent in grams)."""
    return q_pasa(pasa_exact(gold_wt, ratti_kaat))


def value_of_pasa(pasa_value, rate_per_tola):
    """Value = Pasa x Rate per tola / 11.664."""
    return q_money(D(pasa_value) * D(rate_per_tola) / TOLA_GRAMS)


def gold_price(gold_wt, ratti_kaat, rate_per_tola):
    """Price of the gold content. Uses full-precision pasa before rounding, which
    reproduces the workbook (BIN0001: 2.87 g @ 90 ratti, 43,600/tola -> Rs 10,058)."""
    return value_of_pasa(pasa_exact(gold_wt, ratti_kaat), rate_per_tola)


class MakingMode:
    FIXED = "fixed"
    PER_GRAM = "per_gram"
    PER_TOLA = "per_tola"
    PERCENT = "percent"
    CHOICES = [
        (FIXED, "Fixed amount"),
        (PER_GRAM, "Per gram"),
        (PER_TOLA, "Per tola"),
        (PERCENT, "% of gold value"),
    ]


def making_charges(mode, rate, weight, gold_value):
    """Making/labour charge. The owner's exact rule is still an open question,
    so every common mode is supported and the counter picks one per line."""
    rate = D(rate)
    if mode == MakingMode.PER_GRAM:
        return q_money(rate * D(weight))
    if mode == MakingMode.PER_TOLA:
        return q_money(rate * D(weight) / TOLA_GRAMS)
    if mode == MakingMode.PERCENT:
        return q_money(D(gold_value) * rate / Decimal("100"))
    return q_money(rate)


def compute_stock_values(gross, big_stone, pd_diamond, extra_less, ratti_kaat, rate, extra_costs):
    gw = gold_weight(gross, big_stone, pd_diamond, extra_less)
    price = gold_price(gw, ratti_kaat, rate)
    return {
        "gold_weight": gw,
        "pasa": pasa(gw, ratti_kaat),
        "gold_price": price,
        "total_cost": q_money(price + D(extra_costs)),
    }
