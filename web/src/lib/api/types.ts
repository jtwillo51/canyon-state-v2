// Friendly names for the API's response shapes. Safe to import anywhere (types only, no runtime code).
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Partner = Schemas["PartnerOut"];
export type PartnerRow = Schemas["PartnerRow"];
export type Referral = Schemas["ReferralOut"];
export type ReferralStatus = Referral["status"];
export type Step = Schemas["StepOut"];
export type Me = Schemas["Me"];
export type UserRef = Schemas["UserRef"];
export type StatusChange = Schemas["StatusChange"];
export type Progress = Schemas["ProgressOut"];
export type Metric = Schemas["Metric"];
export type RepProgress = Schemas["RepProgress"];
export type Activity = Schemas["ActivityOut"];
export type ActivityIn = Schemas["ActivityIn"];
export type NotificationPage = Schemas["NotificationPage"];
export type Notification = Schemas["NotificationOut"];
export type Digest = Schemas["DigestData"];
export type WeekTally = Schemas["WeekTally"];
export type HistoryEvent = Schemas["HistoryEvent"];
export type FieldChange = Schemas["FieldChange"];
