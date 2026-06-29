/** Singapore home-affordability maths. Public HDB/MAS rules, simplified — every
 *  output is an ESTIMATE, not financial advice. Rules as of 2024/25:
 *   - HDB loan:  MSR 30%, LTV 80%, tenure ≤ 25y, rate 2.6%
 *   - Bank loan: TDSR 55% (and MSR 30% for HDB/EC), LTV 75%, tenure ≤ 30y,
 *                eligibility stress-tested at 4%.
 *  Tenure is also capped so it ends by age 65.
 */
export type LoanType = "hdb" | "bank";

export interface AffordInput {
  monthlyIncome: number;   // gross household
  savings: number;         // cash + CPF OA available for downpayment
  monthlyDebt: number;     // existing monthly debt repayments
  age: number;
  loan: LoanType;
}

export interface AffordResult {
  loanType: LoanType;
  tenureYears: number;
  maxMonthlyRepayment: number;
  maxLoan: number;
  maxPrice: number;
  downpayment: number;        // cash+CPF needed at maxPrice
  monthlyInstalment: number;  // at maxPrice
  limitedBy: "income" | "savings";
  ehgGrant: number;           // estimated Enhanced CPF Housing Grant (families)
}

const RULES = {
  hdb:  { msr: 0.30, tdsr: 1,    ltv: 0.80, maxTenure: 25, rate: 0.026, stress: 0.026 },
  bank: { msr: 0.30, tdsr: 0.55, ltv: 0.75, maxTenure: 30, rate: 0.04,  stress: 0.04 },
};

/** Present value of a level monthly annuity (the max loan a repayment supports). */
function loanFromPayment(monthly: number, annualRate: number, months: number): number {
  const r = annualRate / 12;
  if (months <= 0) return 0;
  if (r === 0) return monthly * months;
  return monthly * (1 - Math.pow(1 + r, -months)) / r;
}

/** Monthly instalment for a loan over a tenure at a rate. */
export function instalment(loan: number, annualRate: number, months: number): number {
  const r = annualRate / 12;
  if (loan <= 0 || months <= 0) return 0;
  if (r === 0) return loan / months;
  return loan * r / (1 - Math.pow(1 + r, -months));
}

/** Estimated Enhanced CPF Housing Grant for families: $80k at ≤$1,500 income,
 *  stepping down $5k per $500 band to $5k near $9,000 (0 above). */
export function estimateEHG(monthlyIncome: number): number {
  if (monthlyIncome <= 1500) return 80000;
  if (monthlyIncome > 9000) return 0;
  const bands = Math.ceil((monthlyIncome - 1500) / 500); // 1..15
  return Math.max(0, 80000 - bands * 5000);
}

export function affordability(input: AffordInput): AffordResult {
  const rules = RULES[input.loan];
  const tenureYears = Math.max(5, Math.min(rules.maxTenure, 65 - Math.max(21, input.age)));
  const months = tenureYears * 12;

  // Repayment capacity: MSR caps the housing instalment; TDSR caps all debts.
  const msrCap = rules.msr * input.monthlyIncome;
  const tdsrCap = rules.tdsr * input.monthlyIncome - input.monthlyDebt;
  const maxMonthlyRepayment = Math.max(0, Math.min(msrCap, tdsrCap));

  // Eligibility uses the (stress) rate; max loan from that repayment.
  const maxLoan = loanFromPayment(maxMonthlyRepayment, rules.stress, months);

  // Price is limited by EITHER the loan (loan = LTV·price) OR the cash/CPF you
  // have for the downpayment (= (1-LTV)·price).
  const priceFromLoan = maxLoan / rules.ltv;
  const priceFromSavings = input.savings / (1 - rules.ltv);
  const maxPrice = Math.max(0, Math.min(priceFromLoan, priceFromSavings));
  const limitedBy: "income" | "savings" = priceFromSavings < priceFromLoan ? "savings" : "income";

  const loanAtPrice = Math.min(maxLoan, maxPrice * rules.ltv);
  const downpayment = maxPrice - loanAtPrice;
  const monthlyInstalment = instalment(loanAtPrice, rules.rate, months);

  return {
    loanType: input.loan,
    tenureYears,
    maxMonthlyRepayment,
    maxLoan,
    maxPrice,
    downpayment,
    monthlyInstalment,
    limitedBy,
    ehgGrant: estimateEHG(input.monthlyIncome),
  };
}
