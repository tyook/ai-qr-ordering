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
  total_price: string;
  created_at: string;
  items: {
    id: number;
    name: string;
    variant_label: string;
    variant_price: string;
    quantity: number;
    special_requests: string;
  }[];
}
