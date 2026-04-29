export type Theme = 'light' | 'dark' | 'system'
export type AccentColor = 'teal' | 'blue' | 'purple' | 'orange' | 'green'
export type WidgetId =
  | 'attention'
  | 'net-position'
  | 'spending-breakdown'
  | 'budget-status'
  | 'recent-transactions'
  | 'investment-snapshot'
  | 'peer-balances'

export interface DateRange {
  from: Date
  to: Date
}

export interface User {
  id: string
  name: string
  phone: string
  created_at: string
}

export interface Account {
  id: string
  type: 'bank' | 'credit_card'
  label: string
  bank_name: string
  last4: string
  is_active: boolean
}

export interface Transaction {
  id: string
  account_id: string
  account_label: string
  date: string
  description: string
  amount_paise: number
  category_id: string | null
  category_name: string | null
  category_icon: string | null
  is_reviewed: boolean
}

export interface Category {
  id: string
  name: string
  icon: string
  color: string
  is_system: boolean
}

export interface BudgetGoal {
  id: string
  category_id: string
  category_name: string
  limit_paise: number
  period: 'monthly' | 'weekly'
  current_spend_paise: number
}

export interface Holding {
  id: string
  name: string
  type: 'mutual_fund' | 'stock' | 'crypto' | 'gold' | 'fd' | 'other'
  units: number
  avg_buy_price_paise: number
  current_value_paise: number
  pnl_paise: number
  pnl_percent: number
}

export interface PeerContact {
  id: string
  name: string
  phone: string | null
  net_balance_paise: number
}

export interface Notification {
  id: string
  type: string
  title: string
  body: string
  is_read: boolean
  created_at: string
}

export interface DashboardWidget {
  id: WidgetId
  label: string
  visible: boolean
  order: number
}
