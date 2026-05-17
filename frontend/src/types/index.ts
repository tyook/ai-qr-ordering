// Subscription types
export interface Subscription {
  plan: "starter" | "growth" | "pro";
  plan_name: string;
  status: "trialing" | "active" | "past_due" | "canceled" | "incomplete";
  trial_end: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  order_count: number;
  order_limit: number;
  overage_count: number;
  is_active: boolean;
}

export interface BillingInvoice {
  id: string;
  date: number;
  amount: number;
  currency: string;
  status: string;
  plan: string;
  receipt_url: string;
}

// Restaurant types
export interface Restaurant {
  id: string;
  name: string;
  slug: string;
  phone: string;
  street_address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  google_place_id: string;
  latitude: number | null;
  longitude: number | null;
  homepage: string;
  logo_url: string;
  tax_rate: string;
  payment_model: "upfront" | "tab";
  accepting_orders: boolean;
  auto_resume_orders: boolean;
  created_at: string;
  subscription?: Subscription;
}

// User types
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  phone: string;
  dietary_preferences: string[];
  allergies: string[];
  preferred_language: string;
  auth_provider: string;
  is_restaurant_owner: boolean;
  owns_restaurant: boolean;
  onboarding_completed: boolean;
  onboarding_dismissed: boolean;
}

export interface AuthResponse {
  user: User;
  access_token?: string;
  refresh_token?: string;
}

// Menu types
export interface MenuItemModifier {
  id: number;
  name: string;
  price_adjustment: string;
}

export interface MenuItemVariant {
  id: number;
  label: string;
  price: string;
  is_default: boolean;
}

export type MenuItemStatus = "active" | "sold_out" | "inactive";

export interface MenuItem {
  id: number;
  name: string;
  description: string;
  image_url: string;
  is_sold_out?: boolean;
  is_featured?: boolean;
  variants: MenuItemVariant[];
  modifiers: MenuItemModifier[];
}

export interface MenuCategory {
  id: number;
  name: string;
  items: MenuItem[];
}

export interface MenuUnavailable {
  available: false;
  restaurant_name: string;
}

export interface PublicMenu {
  available: true;
  restaurant_name: string;
  tax_rate: string;
  payment_mode: "stripe" | "pos_collected";
  payment_model: "upfront" | "tab";
  payment_ready: boolean;
  accepting_orders: boolean;
  categories: MenuCategory[];
  operating_hours: OperatingHoursEntry[];
  holiday_overrides: HolidayOverride[];
}

// Order types
export interface ParsedOrderItem {
  menu_item_id: number;
  name: string;
  description?: string;
  image_url?: string;
  is_featured?: boolean;
  variant: {
    id: number;
    label: string;
    price: string;
  };
  quantity: number;
  modifiers: MenuItemModifier[];
  special_requests: string;
  line_total: string;
}

export interface UnavailableItem {
  name: string;
  reason: "sold_out" | "inactive";
}

export interface ParsedOrderResponse {
  items: ParsedOrderItem[];
  unavailable_items?: UnavailableItem[];
  allergies: string[];
  total_price: string;
  language: string;
}

export interface RecommendationItem {
  menu_item_id: number;
  name: string;
  description: string;
  image_url: string;
  variant_id: number;
  variant_label: string;
  variant_price: string;
  quantity: number;
  reason: string;
  is_featured: boolean;
  modifiers: MenuItemModifier[];
  variants: MenuItemVariant[];
}

export interface RecommendationResponse {
  type: "recommendation";
  items: RecommendationItem[];
}

export interface OrderParseResponse extends ParsedOrderResponse {
  type: "order";
}

export type ParseOrderResult = OrderParseResponse | RecommendationResponse;

export interface ConfirmOrderItem {
  menu_item_id: number;
  variant_id: number;
  quantity: number;
  modifier_ids: number[];
  special_requests: string;
}

export interface OrderResponse {
  id: string;
  status: string;
  table_identifier: string | null;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total_price: string;
  payment_status: string;
  created_at: string;
  customer_allergies: string[];
  items: {
    id: number;
    name: string;
    variant_label: string;
    variant_price: string;
    quantity: number;
    special_requests: string;
    modifiers?: { id: number; name: string; price_adjustment: string }[];
  }[];
}

export interface CreatePaymentResponse extends OrderResponse {
  client_secret: string;
}

export interface OrderHistoryItem extends OrderResponse {
  restaurant_name: string;
  restaurant_slug: string;
}

export interface OrderDetail extends OrderHistoryItem {
  payment_method: {
    brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  } | null;
}

export interface SavedPaymentMethod {
  id: string;
  brand: string;
  last4: string;
  exp_month: number;
  exp_year: number;
}

// POS Integration types
export interface POSConnectionResponse {
  id: string;
  pos_type: "square" | "toast" | "middleware" | "none";
  is_active: boolean;
  payment_mode: "stripe" | "pos_collected";
  external_location_id: string | null;
  is_connected: boolean;
  created_at: string;
  updated_at: string;
}

export interface POSSyncLog {
  id: string;
  order_id: string;
  order_created_at: string;
  status: "pending" | "success" | "failed" | "retrying" | "manually_resolved";
  external_order_id: string | null;
  attempt_count: number;
  last_error: string | null;
  next_retry_at: string | null;
  created_at: string;
}

// Menu Version types
export interface MenuVersion {
  id: number;
  name: string;
  is_active: boolean;
  source: "manual" | "ai_upload";
  created_at: string;
  item_count: number;
}

export interface ParsedMenuVariant {
  label: string;
  price: string;
}

export interface ParsedMenuItem {
  name: string;
  description: string | null;
  image_url: string | null;
  is_featured?: boolean;
  variants: ParsedMenuVariant[];
}

export interface ParsedMenuCategory {
  name: string;
  items: ParsedMenuItem[];
}

export interface ParsedMenu {
  categories: ParsedMenuCategory[];
}

// Table types
export interface Table {
  id: string;
  name: string;
  number: string;
  is_active: boolean;
  created_at: string;
}

// Analytics types
export interface AnalyticsSummary {
  order_count: number;
  total_revenue: number;
  total_tax: number;
  net_revenue: number;
  avg_order_value: number;
  prev_order_count: number;
  prev_total_revenue: number;
}

export interface DailyOrder {
  date: string;
  count: number;
  revenue: number;
}

export interface TopItem {
  name: string;
  quantity: number;
}

export interface PeakHour {
  hour: number;
  orders: number;
}

export interface PaymentBreakdown {
  type: string;
  count: number;
}

export interface AnalyticsResponse {
  period: string;
  summary: AnalyticsSummary;
  daily_orders: DailyOrder[];
  top_items: TopItem[];
  peak_hours: PeakHour[];
  payment_breakdown: PaymentBreakdown[];
}

// Upsell types
export interface UpsellSuggestion {
  menu_item_id: number;
  name: string;
  description: string;
  image_url: string;
  price: string | null;
  variant_id: number | null;
  variant_label: string | null;
  reason: string;
}

export interface CartUpsellResponse {
  suggestions: UpsellSuggestion[];
}

// Tab types
export interface TabOrderItem {
  id: number;
  name: string;
  variant_label: string;
  variant_price: string;
  quantity: number;
  special_requests: string;
  line_total: string;
  modifiers?: { id: number; name: string; price_adjustment: string }[];
}

export interface TabOrder {
  id: string;
  status: string;
  items: TabOrderItem[];
  subtotal: string;
  tax_amount: string;
  total_price: string;
  created_at: string;
}

export interface TabResponse {
  id: string;
  table_identifier: string;
  status: "open" | "closing" | "closed";
  orders: TabOrder[];
  subtotal: string;
  tax_amount: string;
  total: string;
  amount_paid: string;
  amount_remaining: string;
  opened_at: string;
}

export interface TabOrderResponse extends OrderResponse {
  tab: TabResponse;
}

export interface TabPaymentResponse {
  payment_id: string;
  client_secret: string;
}

// Operating Hours types
export interface OperatingHoursEntry {
  id?: number;
  day_of_week: number;
  open_time: string;
  close_time: string;
}

export interface HolidayOverride {
  id: number;
  date: string;
  label: string;
  is_closed: boolean;
  open_time: string | null;
  close_time: string | null;
}

// Hall Status types
export interface HallStatusOrderItem {
  id: number;
  name: string;
  variant_label: string;
  quantity: number;
}

export interface HallStatusOrder {
  id: string;
  status: string;
  total_price: string;
  created_at: string;
  items: HallStatusOrderItem[];
}

export interface HallStatusTab {
  id: string;
  status: string;
  total: string;
  order_count: number;
  opened_at: string;
  first_order_at: string | null;
  orders: HallStatusOrder[];
}

export interface HallStatusTable {
  id: string;
  name: string;
  number: string;
  has_tab: boolean;
  tab: HallStatusTab | null;
}
