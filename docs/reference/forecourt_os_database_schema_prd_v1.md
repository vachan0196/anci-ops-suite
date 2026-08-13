# Forecourt_OS Database Schema PRD

**File name:** `forecourt_os_database_schema_prd_v1.md`  
**Version:** 1.0  
**Status:** Draft database architecture source of truth  
**Product:** Forecourt_OS  
**Database:** PostgreSQL  
**ORM:** SQLAlchemy 2.0  
**Migrations:** Alembic only  

---

## 1. Purpose

This document defines the intended database schema direction for Forecourt_OS.

It is not a complete final physical schema. It is a product-aware database PRD that guides developers and AI coding agents when creating models, migrations, relationships, indexes, and constraints.

The database must support:

- multi-tenant SaaS
- multiple sites per tenant
- Owner/Admin/Manager/Employee role separation
- site-specific employee accounts
- rota management
- availability
- leave/swap/cover requests
- payroll calculation visibility
- employee earnings
- hot food forecasting and actuals
- sales manual entries
- reports
- AI actions
- notifications
- billing/subscriptions
- audit logs
- file metadata
- lifecycle controls

---

## 2. Database Principles

The schema must follow these principles:

- PostgreSQL is the primary database.
- SQLAlchemy 2.0 is the ORM.
- Alembic controls all schema changes.
- No `create_all()` in runtime application startup.
- UUID primary keys are preferred.
- Tenant-owned data must include `tenant_id`.
- Site-specific data must include `site_id`.
- Sensitive access must be audit logged.
- Soft delete/archive is preferred for operational records.
- Hard delete/full erasure must be restricted.
- Tables must support future reporting and audit needs.
- Request bodies must never decide tenant ownership.
- Database relationships must support tenant and site isolation.

---

## 3. Naming Conventions

Use snake_case.

Examples:

```text
tenant_id
site_id
created_at
updated_at
archived_at
is_active
```

Table names should be plural where practical:

```text
tenants
users
sites
staff_profiles
shifts
audit_logs
```

---

## 4. Common Columns

Most tables should include:

```text
id UUID PRIMARY KEY
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE nullable
```

Tenant-owned tables should include:

```text
tenant_id UUID NOT NULL
```

Site-specific tables should include:

```text
site_id UUID NOT NULL
```

Soft-delete/archive capable tables may include:

```text
is_active BOOLEAN DEFAULT TRUE
archived_at TIMESTAMP WITH TIME ZONE NULL
archived_by_user_id UUID NULL
archive_reason TEXT NULL
```

Sensitive tables may include:

```text
sensitivity_level TEXT
```

---

## 5. Core Identity Tables

## 5.1 tenants

Purpose:

Represents a customer company/business.

Suggested fields:

```text
id UUID PK
name TEXT NOT NULL
business_email TEXT
phone_number TEXT
registered_address TEXT
subscription_state TEXT NOT NULL
trial_start TIMESTAMP WITH TIME ZONE
trial_end TIMESTAMP WITH TIME ZONE
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
archived_at TIMESTAMP WITH TIME ZONE
fully_erased_at TIMESTAMP WITH TIME ZONE
```

Rules:

- one tenant represents one customer/company
- tenant lifecycle is Platform Owner controlled for suspension/reactivation/full erasure
- tenant subscription state controls access

Indexes:

```text
subscription_state
created_at
```

---

## 5.2 users

Purpose:

Represents admin-side identity users and internal platform users.

Suggested fields:

```text
id UUID PK
email TEXT UNIQUE
hashed_password TEXT NULL
full_name TEXT
is_active BOOLEAN DEFAULT TRUE
email_verified_at TIMESTAMP WITH TIME ZONE NULL
active_tenant_id UUID NULL
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
last_login_at TIMESTAMP WITH TIME ZONE NULL
```

Rules:

- used for Owner/Admin/Manager and Platform Owner where applicable
- employee site-specific login may use separate employee account table
- no plain text passwords
- Google sign-in users may have nullable password

Indexes:

```text
email
active_tenant_id
is_active
```

---

## 5.3 tenant_users

Purpose:

Links users to tenants and roles.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
user_id UUID NOT NULL
role TEXT NOT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Roles:

```text
owner
admin
manager
member
```

Constraints:

```text
UNIQUE (tenant_id, user_id)
```

Indexes:

```text
tenant_id
user_id
(tenant_id, role)
```

---

## 5.4 site_user_assignments

Purpose:

Links admin-side users to sites they can access.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
user_id UUID NOT NULL
site_role TEXT NOT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Rules:

- Owner may have implicit all-site access
- Admin/Manager require site assignments
- removing a Manager from a site removes access to that site only

Constraints:

```text
UNIQUE (tenant_id, site_id, user_id)
```

Indexes:

```text
(tenant_id, site_id)
(tenant_id, user_id)
```

---

# 6. Site and Company Tables

## 6.1 sites

Purpose:

Represents physical forecourt/convenience retail locations.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
name TEXT NOT NULL
code TEXT NOT NULL
address_line1 TEXT
address_line2 TEXT
city TEXT
postcode TEXT
phone_number TEXT
email TEXT
timezone TEXT DEFAULT 'Europe/London'
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
archived_at TIMESTAMP WITH TIME ZONE NULL
```

Constraints:

```text
UNIQUE (tenant_id, code)
```

Indexes:

```text
tenant_id
(tenant_id, code)
is_active
```

---

## 6.2 site_opening_hours

Purpose:

Stores site opening hours.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
day_of_week INT NOT NULL
open_time TIME
close_time TIME
is_closed BOOLEAN DEFAULT FALSE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Constraints:

```text
UNIQUE (tenant_id, site_id, day_of_week)
```

---

## 6.3 site_settings

Purpose:

Stores site-specific operational settings.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
business_week_start_day INT DEFAULT 0
rota_publish_policy JSONB
notification_policy JSONB
ai_policy JSONB
hot_food_policy JSONB
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

---

# 7. Employee and Workforce Tables

## 7.1 employee_accounts

Purpose:

Represents site-specific employee login accounts.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
username TEXT NOT NULL
hashed_password TEXT NOT NULL
display_name TEXT NOT NULL
email TEXT NULL
phone_number TEXT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
last_login_at TIMESTAMP WITH TIME ZONE NULL
password_changed_at TIMESTAMP WITH TIME ZONE NULL
```

Rules:

- username is unique within site
- employee login is site selection + username/password
- employees cannot use email login in MVP
- employee account is separate per site in MVP

Constraints:

```text
UNIQUE (tenant_id, site_id, username)
```

Indexes:

```text
(tenant_id, site_id)
(tenant_id, site_id, username)
```

---

## 7.2 staff_profiles

Purpose:

Stores employee operational profile and workforce metadata.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
employee_account_id UUID NULL
user_id UUID NULL
display_name TEXT NOT NULL
job_title TEXT
phone_number TEXT
email TEXT
contract_type TEXT
base_pay_rate NUMERIC(10,2)
base_hours NUMERIC(8,2)
overtime_rate NUMERIC(10,2)
weekly_hour_cap NUMERIC(8,2)
right_to_work_status TEXT
document_type TEXT
document_expiry_date DATE
notes TEXT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
archived_at TIMESTAMP WITH TIME ZONE NULL
```

Rules:

- employee profile is site-specific in MVP
- pay rules are employee-specific
- sensitive fields must be access-controlled
- profile changes must be audit logged

Indexes:

```text
tenant_id
site_id
(tenant_id, site_id)
employee_account_id
```

---

## 7.3 skill_tags

Purpose:

Stores tenant/site skill tags.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NULL
name TEXT NOT NULL
normalized_name TEXT NOT NULL
created_at TIMESTAMP WITH TIME ZONE
```

Rules:

- Owner controls master skill tags
- skill tags may be tenant-wide or site-specific depending on final implementation

Constraints:

```text
UNIQUE (tenant_id, site_id, normalized_name)
```

---

## 7.4 staff_skill_tags

Purpose:

Links staff profiles to skill tags.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
staff_profile_id UUID NOT NULL
skill_tag_id UUID NOT NULL
created_at TIMESTAMP WITH TIME ZONE
```

Constraints:

```text
UNIQUE (tenant_id, site_id, staff_profile_id, skill_tag_id)
```

---

# 8. Rota and Shift Tables

## 8.1 shifts

Purpose:

Represents atomic rota blocks.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
assigned_employee_account_id UUID NULL
assigned_user_id UUID NULL
role_required TEXT NULL
start_time TIMESTAMP WITH TIME ZONE NOT NULL
end_time TIMESTAMP WITH TIME ZONE NOT NULL
status TEXT NOT NULL
published_at TIMESTAMP WITH TIME ZONE NULL
created_by_user_id UUID NULL
updated_by_user_id UUID NULL
role_override BOOLEAN DEFAULT FALSE
availability_override BOOLEAN DEFAULT FALSE
overridden_by_user_id UUID NULL
overridden_at TIMESTAMP WITH TIME ZONE NULL
override_reason TEXT NULL
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Statuses:

```text
scheduled
cancelled
completed
```

Indexes:

```text
(tenant_id, site_id, start_time)
(tenant_id, site_id, published_at)
assigned_employee_account_id
status
```

---

## 8.2 coverage_templates

Purpose:

Defines reusable staffing demand patterns.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
day_of_week INT NOT NULL
start_time TIME NOT NULL
end_time TIME NOT NULL
required_headcount INT NOT NULL
required_role TEXT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Rules:

- required_headcount must be >= 1
- end_time must be after start_time
- templates are site-scoped

Indexes:

```text
(tenant_id, site_id)
(tenant_id, site_id, day_of_week)
```

---

## 8.3 availability_entries

Purpose:

Stores employee availability.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
employee_account_id UUID NOT NULL
week_start DATE NOT NULL
day_of_week INT NOT NULL
start_time TIME
end_time TIME
status TEXT NOT NULL
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Statuses:

```text
available
unavailable
available_extra
```

Rules:

- employees can edit future availability only before rota is published
- Owner override must be audit logged

Indexes:

```text
(tenant_id, site_id, employee_account_id)
(tenant_id, site_id, week_start)
```

---

## 8.4 shift_requests

Purpose:

Stores leave, swap, drop, pickup, and cover requests.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
shift_id UUID NULL
requester_employee_account_id UUID NOT NULL
target_employee_account_id UUID NULL
request_type TEXT NOT NULL
status TEXT NOT NULL
reason TEXT NOT NULL
approver_user_id UUID NULL
approval_reason TEXT NULL
rejection_reason TEXT NULL
decided_at TIMESTAMP WITH TIME ZONE NULL
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Request types:

```text
leave
swap
cover
drop
pickup
```

Statuses:

```text
pending
target_accepted
target_declined
approved
rejected
cancelled
```

Indexes:

```text
(tenant_id, site_id)
(tenant_id, site_id, requester_employee_account_id)
(tenant_id, site_id, status)
```

---

# 9. Payroll and Earnings Tables

## 9.1 payroll_rules

Purpose:

Stores employee-specific pay rules.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
employee_account_id UUID NOT NULL
base_pay_rate NUMERIC(10,2) NOT NULL
base_hours NUMERIC(8,2) NOT NULL
overtime_rate NUMERIC(10,2) NOT NULL
weekly_hour_cap NUMERIC(8,2)
effective_from DATE NOT NULL
effective_to DATE NULL
created_by_user_id UUID
created_at TIMESTAMP WITH TIME ZONE
```

Rules:

- pay rules are employee-specific
- changes are Owner-only and audit logged
- historical effective dating is recommended

Indexes:

```text
(tenant_id, site_id, employee_account_id)
effective_from
```

---

## 9.2 earnings_snapshots

Purpose:

Stores calculated earnings snapshots for employee portal/reporting.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
employee_account_id UUID NOT NULL
period_type TEXT NOT NULL
period_start DATE NOT NULL
period_end DATE NOT NULL
base_hours_worked NUMERIC(8,2)
overtime_hours_worked NUMERIC(8,2)
base_pay_amount NUMERIC(10,2)
overtime_pay_amount NUMERIC(10,2)
total_earnings NUMERIC(10,2)
calculated_at TIMESTAMP WITH TIME ZONE
source_version TEXT
```

Period types:

```text
week
month
custom
```

Rules:

- derived from published rota state
- recalculates when published rota changes
- not actual payment processing

Indexes:

```text
(tenant_id, site_id, employee_account_id)
(period_start, period_end)
```

---

## 9.3 payroll_adjustments

Purpose:

Stores manual payroll adjustments.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
employee_account_id UUID NOT NULL
amount NUMERIC(10,2) NOT NULL
reason TEXT NOT NULL
created_by_user_id UUID NOT NULL
created_at TIMESTAMP WITH TIME ZONE
```

Rules:

- Owner-only in MVP
- audit logged
- does not process payments

---

# 10. Sales and Hot Food Tables

## 10.1 sales_categories

Purpose:

Stores configurable sales categories/departments.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
name TEXT NOT NULL
normalized_name TEXT NOT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
```

Constraints:

```text
UNIQUE (tenant_id, site_id, normalized_name)
```

---

## 10.2 sales_entries

Purpose:

Stores manual sales entries.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
sales_date DATE NOT NULL
category_id UUID NULL
amount NUMERIC(12,2) NOT NULL
quantity NUMERIC(12,2) NULL
entry_type TEXT NOT NULL
notes TEXT NULL
created_by_user_id UUID
updated_by_user_id UUID
is_deleted BOOLEAN DEFAULT FALSE
deleted_at TIMESTAMP WITH TIME ZONE NULL
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Entry types:

```text
fuel_sales
shop_sales
bunkered_product_sales
returns
cash_movement
department_total
```

Rules:

- manual-entry first in MVP
- edits overwrite values but are audit logged
- deletes are soft deletes

Indexes:

```text
(tenant_id, site_id, sales_date)
(tenant_id, site_id, category_id)
```

---

## 10.3 hot_food_items

Purpose:

Stores hot food master items per site.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
name TEXT NOT NULL
normalized_name TEXT NOT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Constraints:

```text
UNIQUE (tenant_id, site_id, normalized_name)
```

---

## 10.4 hot_food_actuals

Purpose:

Stores manual actuals for hot food operations.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
item_id UUID NOT NULL
business_date DATE NOT NULL
prep_window TEXT NULL
quantity_prepared INT NOT NULL
quantity_sold INT NOT NULL
quantity_wasted INT NOT NULL
waste_cost NUMERIC(10,2) NULL
created_by_user_id UUID
updated_by_user_id UUID
is_deleted BOOLEAN DEFAULT FALSE
deleted_at TIMESTAMP WITH TIME ZONE NULL
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Rules:

- manual-entry first in MVP
- edits/deletes audit logged
- site-scoped

Indexes:

```text
(tenant_id, site_id, business_date)
(tenant_id, site_id, item_id)
```

---

## 10.5 hot_food_forecasts

Purpose:

Stores generated forecasts/recommendations.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
item_id UUID NOT NULL
forecast_date DATE NOT NULL
recommended_prep_quantity INT
forecast_quantity INT
confidence_level TEXT
method TEXT
input_data_version TEXT
generated_by TEXT
created_at TIMESTAMP WITH TIME ZONE
invalidated_at TIMESTAMP WITH TIME ZONE NULL
```

Rules:

- new sites may use rule-based guidance
- stronger forecasting after usable history exists
- forecasts become stale if inputs change

---

# 11. Reporting and Export Tables

## 11.1 report_exports

Purpose:

Tracks generated exports.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NULL
requested_by_user_id UUID NOT NULL
requested_by_employee_account_id UUID NULL
report_type TEXT NOT NULL
format TEXT NOT NULL
status TEXT NOT NULL
storage_key TEXT NULL
date_range_start DATE NULL
date_range_end DATE NULL
created_at TIMESTAMP WITH TIME ZONE
completed_at TIMESTAMP WITH TIME ZONE NULL
expires_at TIMESTAMP WITH TIME ZONE NULL
```

Formats:

```text
pdf
csv
xlsx
```

Rules:

- exports require permission check
- suspended tenants cannot export
- employee exports are current-site only
- removed employee history excluded unless restored

---

# 12. AI Tables

## 12.1 ai_action_logs

Purpose:

Tracks AI suggestions, drafts, confirmations, and executions.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NULL
user_id UUID NULL
employee_account_id UUID NULL
module TEXT NOT NULL
action_type TEXT NOT NULL
status TEXT NOT NULL
ai_provider TEXT
model_name TEXT
input_summary TEXT NULL
output_summary TEXT NULL
requires_confirmation BOOLEAN DEFAULT FALSE
confirmed_by_user_id UUID NULL
confirmed_at TIMESTAMP WITH TIME ZONE NULL
executed_at TIMESTAMP WITH TIME ZONE NULL
invalidated_at TIMESTAMP WITH TIME ZONE NULL
created_at TIMESTAMP WITH TIME ZONE
```

Statuses:

```text
suggestion_only
draft_created
awaiting_confirmation
confirmed
executed
rejected
invalidated
reversed
blocked
```

---

## 12.2 ai_help_conversations

Purpose:

Stores Employee AI Help conversation metadata/history.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
employee_account_id UUID NOT NULL
title TEXT NULL
is_visible_to_employee BOOLEAN DEFAULT TRUE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
hidden_at TIMESTAMP WITH TIME ZONE NULL
```

Rules:

- admin side cannot view Employee AI Help history in MVP
- employee can hide/restore visible history
- real records remain in system history

---

# 13. Notification Tables

## 13.1 notification_rules

Purpose:

Stores site-specific notification rules.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NOT NULL
event_type TEXT NOT NULL
channel TEXT NOT NULL
is_enabled BOOLEAN DEFAULT TRUE
created_by_user_id UUID
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

Channels:

```text
in_product
sms
whatsapp
```

---

## 13.2 notifications

Purpose:

Stores in-product notifications and outbound notification records.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
site_id UUID NULL
recipient_user_id UUID NULL
recipient_employee_account_id UUID NULL
event_type TEXT NOT NULL
channel TEXT NOT NULL
title TEXT NOT NULL
body TEXT NOT NULL
status TEXT NOT NULL
provider_message_id TEXT NULL
created_at TIMESTAMP WITH TIME ZONE
sent_at TIMESTAMP WITH TIME ZONE NULL
read_at TIMESTAMP WITH TIME ZONE NULL
```

---

# 14. Billing Tables

## 14.1 billing_customers

Purpose:

Links tenants to Stripe customers.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL UNIQUE
stripe_customer_id TEXT NOT NULL
billing_email TEXT
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

---

## 14.2 subscriptions

Purpose:

Stores subscription state.

Suggested fields:

```text
id UUID PK
tenant_id UUID NOT NULL
stripe_subscription_id TEXT UNIQUE
stripe_price_id TEXT
status TEXT NOT NULL
site_quantity INT NOT NULL
trial_start TIMESTAMP WITH TIME ZONE NULL
trial_end TIMESTAMP WITH TIME ZONE NULL
current_period_start TIMESTAMP WITH TIME ZONE NULL
current_period_end TIMESTAMP WITH TIME ZONE NULL
cancel_at_period_end BOOLEAN DEFAULT FALSE
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

---

## 14.3 billing_events

Purpose:

Stores Stripe webhook/billing event history.

Suggested fields:

```text
id UUID PK
tenant_id UUID NULL
stripe_event_id TEXT UNIQUE NOT NULL
event_type TEXT NOT NULL
processing_status TEXT NOT NULL
payload_summary JSONB NULL
received_at TIMESTAMP WITH TIME ZONE
processed_at TIMESTAMP WITH TIME ZONE NULL
```

---

# 15. Audit Tables

## 15.1 audit_logs

Purpose:

Tracks important actions.

Suggested fields:

```text
id UUID PK
tenant_id UUID NULL
site_id UUID NULL
actor_user_id UUID NULL
actor_employee_account_id UUID NULL
actor_role TEXT NULL
action TEXT NOT NULL
entity_type TEXT NOT NULL
entity_id UUID NULL
before_value JSONB NULL
after_value JSONB NULL
metadata JSONB NULL
ip_address TEXT NULL
user_agent TEXT NULL
request_id TEXT NULL
ai_involved BOOLEAN DEFAULT FALSE
sensitivity_level TEXT DEFAULT 'normal'
created_at TIMESTAMP WITH TIME ZONE
```

Indexes:

```text
tenant_id
site_id
actor_user_id
actor_employee_account_id
entity_type
entity_id
created_at
sensitivity_level
```

---

# 16. Migration Rules

Every schema change must:

- have an Alembic migration
- be reversible where practical
- avoid destructive changes without review
- include indexes for expected query patterns
- include constraints where data integrity matters
- be tested locally and in CI
- not rely on `create_all()`

---

# 17. Testing Requirements

Database-related tests must cover:

- tenant isolation
- site isolation
- Owner/Admin/Manager/Employee permissions
- employee self-only access
- suspended tenant behaviour
- soft delete/archive behaviour
- audit log creation
- AI action logging
- billing webhook idempotency
- report/export permissions
- sensitive data access restrictions

---

# 18. Final Schema Rule

Every new table must answer:

- Does it belong to a tenant?
- Does it belong to a site?
- Is it sensitive?
- Who can read it?
- Who can write it?
- Should changes be audit logged?
- Can AI access it?
- Can it be exported?
- Can it be cached offline?
- What happens when the tenant/site/user is disabled?

If these questions are unclear, the table design is not ready.
