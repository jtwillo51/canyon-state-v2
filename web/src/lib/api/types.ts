// Friendly names for the API's response shapes. Safe to import anywhere (types only, no runtime code).
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Partner = Schemas["PartnerOut"];
export type Referral = Schemas["ReferralOut"];
export type ReferralStatus = Referral["status"];
export type Step = Schemas["StepOut"];
