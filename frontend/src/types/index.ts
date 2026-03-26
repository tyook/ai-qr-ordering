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

// Restaurant types
export interface Restaurant {
  id: string;
  name: string;
  slug: string;
  phone: string;
  address: string;
  homepage: string;
  logo_url: string;
  tax_rate: string;
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
}

export interface AuthResponse {
  user: User;
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

export interface MenuItem {
  id: number;
  name: string;
  description: string;
  image_url: string;
  variants: MenuItemVariant[];
  modifiers: MenuItemModifier[];
}

export interface MenuCategory {
  id: number;
  name: string;
  items: MenuItem[];
}

export interface PublicMenu {
  restaurant_name: string;
  tax_rate: string;
  payment_mode: "stripe" | "pos_collected";
  categories: MenuCategory[];
}

// Order types
export interface ParsedOrderItem {
  menu_item_id: number;
  name: string;
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

export interface ParsedOrderResponse {
  items: ParsedOrderItem[];
  allergies: string[];
  total_price: string;
  language: string;
}

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
