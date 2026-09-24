// Client-side mirror of backend/core/calculations.py — for instant feedback only.
// The server recalculates everything on save; these numbers are never sent as truth.
import { toNum } from "./format";

export const TOLA_GRAMS = 11.664;

export const goldWeight = (gross, stone, pd, extra) => toNum(gross) - toNum(stone) - toNum(pd) + toNum(extra);
export const pasaOf = (goldWt, ratti) => (toNum(goldWt) * toNum(ratti)) / 96;
export const valueOfPasa = (pasa, rate) => Math.round((toNum(pasa) * toNum(rate)) / TOLA_GRAMS);

export function stockCost({ gross_weight, big_stone_weight, pd_diamond_weight, extra_less_gold, ratti_kaat, purchase_rate, extra_costs }) {
  const gw = goldWeight(gross_weight, big_stone_weight, pd_diamond_weight, extra_less_gold);
  const p = pasaOf(gw, ratti_kaat);
  const price = valueOfPasa(p, purchase_rate);
  return { gold_weight: gw, pasa: p, gold_price: price, total_cost: price + Math.round(toNum(extra_costs)) };
}
