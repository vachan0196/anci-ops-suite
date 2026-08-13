\# Forecourt\_OS Technical Architecture PRD

\*\*File name:\*\* \`forecourt\_os\_technical\_architecture\_prd\_v1.md\`    
\*\*Version:\*\* 1.0    
\*\*Status:\*\* Draft technical source of truth    
\*\*Product:\*\* Forecourt\_OS    
\*\*Market:\*\* UK-first    
\*\*Product Type:\*\* B2B SaaS    
\*\*Architecture Type:\*\* Multi-tenant SaaS platform    
\*\*Primary Users:\*\* Owner, Admin, Manager, Employee, Platform Owner / Super Admin  

\---

\#\# Version 1.0 Purpose

This document defines the recommended technical architecture, development stack, cloud setup, security model, billing architecture, data protection rules, AI safety boundaries, observability, deployment approach, and operational controls for Forecourt\_OS.

This document is designed to help:

\- AI coding agents understand the intended technical direction  
\- developers follow a consistent architecture  
\- future contributors avoid unsafe shortcuts  
\- the product remain secure, scalable, auditable, and maintainable  
\- the team build with UK GDPR-aware and SaaS-grade practices from the beginning

This document should be treated as a technical companion to:

\- \`forecourt\_os\_prd\_v1.md\`  
\- \`forecourt\_os\_prd\_v1\_1.md\`  
\- onboarding and login documentation  
\- backend implementation progress documents

\---

\#\# Important Compliance Disclaimer

This technical architecture is designed to support a secure, UK GDPR-aware, multi-tenant SaaS platform.

However, this document does \*\*not\*\* guarantee legal compliance by itself.

Legal and regulatory compliance depends on:

\- correct implementation  
\- secure operational practices  
\- legal review  
\- privacy documentation  
\- customer contracts  
\- data-processing agreements  
\- incident response procedures  
\- monitoring  
\- testing  
\- security reviews  
\- staff access controls  
\- ongoing governance

Forecourt\_OS must be built with security-by-design, privacy-by-design, auditability, and least-privilege access principles from day one.

\---

\# 1\. Purpose

The purpose of this document is to define the technical foundation for Forecourt\_OS.

Forecourt\_OS is an AI-first workforce and operations platform for forecourt and convenience retail businesses. It supports:

\- rota planning  
\- staff management  
\- site-based operations  
\- payroll calculation visibility  
\- employee earnings visibility  
\- hot food forecasting and waste tracking  
\- sales and labour reporting  
\- AI-assisted recommendations  
\- notifications  
\- audit logging  
\- billing and subscription management  
\- employee portal workflows  
\- admin portal workflows

The architecture must support:

\- multi-tenant SaaS  
\- multiple sites per tenant  
\- strict tenant isolation  
\- strict site-scoped access  
\- separate Admin and Employee portal experiences  
\- sensitive payroll and compliance data protection  
\- AI actions with human approval  
\- subscription billing  
\- scalable cloud deployment  
\- secure file storage  
\- auditability  
\- future growth

\---

\# 2\. Source of Truth

The current product requirements source of truth is:

\`\`\`text  
forecourt\_os\_prd\_v1\_1.md

Version 1.1 locks important MVP rules including:

Owner-only governance

employee site-specific accounts

admin and employee portal separation

payroll visibility but not payment processing

manual sales and hot food data input first

report exports

mobile-first product experience

limited offline cached viewing

AI action boundaries

notification rules

audit requirements

sensitive access controls

2FA requirements for sensitive areas/actions

The technical architecture must not contradict the product PRD.

If this technical document conflicts with the product PRD, the product PRD should be reviewed and both documents should be updated together.

\---

3\. Architecture Principles

3.1 Security First

Security is not optional.

Every technical decision must protect:

tenant data

employee data

payroll-related information

compliance documents

right-to-work information

authentication credentials

billing data

AI-accessible data

audit history

Security must be designed into the platform, not added later.

\---

3.2 Privacy by Design

Forecourt\_OS must collect only the data it needs.

The product must avoid unnecessary personal data collection.

Sensitive data must be:

minimised

encrypted where appropriate

access-controlled

audit-logged

protected from offline caching

excluded from AI access unless explicitly allowed

removed or retained according to defined retention rules

\---

3.3 Tenant Isolation by Default

Forecourt\_OS is a multi-tenant SaaS product.

Tenant isolation must be enforced at every layer:

database queries

API endpoints

background jobs

file storage

AI context retrieval

notifications

reporting

exports

audit logs

No tenant should ever be able to access another tenant’s data.

\---

3.4 Site Scope by Default

Within a tenant, most operational data is site-specific.

Site assignment controls:

rota access

employee portal access

reports

hot food data

sales data

notifications

AI scope

exports

requests

earnings visibility

Users must only access sites they are assigned to or authorised to manage.

\---

3.5 Human Control Over AI

AI is an assistance layer, not the final authority.

AI can:

recommend

explain

generate drafts

prepare actions

assist exports

answer allowed questions

perform allowed actions after confirmation

AI cannot:

bypass permissions

access unauthorised data

auto-publish rota

auto-approve sensitive actions

change billing rules

change authentication rules

change 2FA rules

change data-retention rules

erase data

mix tenant or site data

\---

3.6 Audit Everything Important

The platform must maintain audit logs for important actions, especially:

authentication events

failed login attempts

sensitive data access

payroll access

compliance document access

profile changes

pay rule changes

rota publishing

request approvals

AI-generated drafts

AI-approved actions

AI reversals

billing events

subscription state changes

destructive actions

data exports

permission changes

\---

3.7 Build for MVP, But Avoid Dead Ends

The architecture should support the MVP without overengineering.

However, it must not create technical dead ends.

The system should be modular enough to support future:

native mobile apps

POS/EPOS integrations

advanced forecasting

advanced reporting

advanced AI assistants

payroll export integrations

enterprise tenant controls

stronger compliance workflows

multi-region deployment if required later

\---

4\. Recommended Tech Stack

4.1 Frontend

Recommended stack:

Next.js  
TypeScript  
React  
Tailwind CSS  
shadcn/ui  
React Hook Form  
Zod  
TanStack Query

Reasoning

Next.js with TypeScript is suitable for a modern SaaS dashboard because it supports:

strong typing

scalable frontend architecture

mobile-first responsive design

server-side rendering where useful

reusable UI components

admin and employee portal separation

future PWA support

Frontend Rules

The frontend must:

be mobile-first

support desktop layouts

separate Admin Portal and Employee Portal views

enforce route protection

never rely only on frontend permissions

handle expired sessions safely

show permission-based UI

avoid exposing sensitive fields in client state

avoid storing sensitive data in local storage

never cache sensitive payroll/compliance data offline

\---

4.2 Backend

Recommended stack:

FastAPI  
Python  
SQLAlchemy 2.0  
Alembic  
Pydantic  
Pytest

Reasoning

FastAPI is already aligned with the current backend direction.

It supports:

typed API contracts

modular routers

async-friendly architecture

strong validation

OpenAPI documentation

clean dependency injection

scalable API development

Backend Rules

The backend must:

use versioned API routes

use structured error responses

use dependency-based authentication

enforce tenant context on every protected request

enforce site scope where applicable

use Alembic migrations only

never use create\_all() in application startup

include automated tests for isolation, permissions, and sensitive actions

\---

4.3 Database

Recommended database:

PostgreSQL

Reasoning

PostgreSQL is suitable for:

multi-tenant SaaS data

relational workforce data

audit logs

billing records

reporting foundations

structured payroll calculations

rota and scheduling logic

JSONB fields where needed later

strong indexing

future analytics pipelines

\---

4.4 Cache and Background Jobs

Recommended stack:

Redis  
Celery or Dramatiq

Uses

Redis can support:

rate limiting

temporary session/token storage

background job queues

short-lived locks

caching non-sensitive data

export generation job status

AI job status tracking

Background workers can support:

report exports

AI report generation

notification dispatch

billing webhook processing

scheduled cleanup jobs

backup validation tasks

async audit enrichment

hot food forecast batch jobs

Sensitive data must not be stored casually in Redis.

If sensitive data must be temporarily stored, it must be:

encrypted where appropriate

short-lived

access-controlled

automatically expired

\---

4.5 File Storage

Recommended storage:

AWS S3 private buckets

Used for:

right-to-work documents

compliance files

generated PDF exports

generated CSV/Excel exports

audit export files

AI governance report exports

temporary downloadable reports

Files must not be public.

All access must use controlled backend authorization and short-lived signed URLs.

\---

4.6 Payments

Recommended provider:

Stripe Billing  
Stripe Checkout  
Stripe Customer Portal  
Stripe Webhooks

Forecourt\_OS must not store raw card data.

Stripe should handle:

card collection

subscription setup

billing portal

payment method updates

invoices

payment retries where possible

payment status events

Forecourt\_OS stores only:

Stripe customer ID

Stripe subscription ID

Stripe price ID

Stripe invoice ID

subscription state

trial dates

current billing period

site count billing quantity

billing event logs

\---

4.7 Notifications

Recommended provider:

Twilio

For MVP notification channels:

in-product notifications

SMS

WhatsApp

Email and push notifications are not required in MVP unless added later.

\---

4.8 AI Provider

Recommended approach:

OpenAI API first  
Internal AI service abstraction layer

The product should not call AI providers directly from random modules.

All AI requests must go through a controlled internal AI layer.

The AI layer must enforce:

tenant scope

site scope

user role

permission checks

data minimisation

prompt logging policy

output logging policy

approval state tracking

safety boundaries

\---

4.9 Observability

Recommended stack:

AWS CloudWatch  
Sentry  
Structured JSON logs  
Request IDs  
Audit logs

Used for:

API errors

frontend errors

background job errors

slow requests

failed login spikes

billing webhook failures

AI failures

notification failures

suspicious activity detection

\---

4.10 CI/CD

Recommended stack:

GitHub  
GitHub Actions  
Docker  
AWS ECS Fargate

CI/CD should run:

formatting checks

linting

type checks

unit tests

integration tests

migration checks

Docker build checks

security dependency scanning

deployment approval gates

\---

5\. Cloud Architecture

5.1 Recommended Cloud Provider

Recommended provider:

AWS

AWS is recommended because it supports:

scalable container hosting

managed PostgreSQL

private file storage

secrets management

logging

monitoring

CDN support

IAM access controls

mature SaaS architecture patterns

UK/EU region options

\---

5.2 Recommended AWS Services

Application Hosting

AWS ECS Fargate

Used for:

FastAPI backend container

background worker containers

scheduled task containers

Database

Amazon RDS for PostgreSQL

Used for production PostgreSQL.

File Storage

Amazon S3

Used for private documents and generated exports.

Secrets

AWS Secrets Manager

Used for:

database credentials

JWT secrets

Stripe keys

Twilio keys

OpenAI keys

encryption keys where applicable

Logs and Monitoring

AWS CloudWatch

Used for:

application logs

infrastructure logs

alarms

metrics

Load Balancing

Application Load Balancer

Used to route HTTPS traffic to backend containers.

CDN and Static Assets

CloudFront

Can be used later for frontend hosting and static assets.

Frontend Hosting

Options:

Vercel for speed  
AWS Amplify  
AWS ECS/CloudFront/S3 architecture

For MVP speed, Vercel is acceptable for the frontend if security and environment management are handled properly.

For tighter AWS consolidation, AWS-native hosting can be used later.

\---

5.3 AWS Region

Recommended production region:

eu-west-2

Reason:

UK London region

aligns with UK-first product positioning

supports UK-based data residency preference

Alternative region:

eu-west-1

Reason:

Ireland region

commonly used for EU/UK SaaS products

mature AWS service availability

Final region should be confirmed before production launch.

\---

6\. Database and Storage Architecture

6.1 Primary Database

Forecourt\_OS uses PostgreSQL as the primary relational database.

The database stores:

tenants

users

tenant memberships

sites

staff profiles

employee accounts

roles and permissions

shifts

rota data

availability

requests

payroll calculation records

earnings records

hot food data

sales entries

reporting categories

notification settings

billing records

audit logs

AI action records

export metadata

\---

6.2 Database Migration Rules

Database schema changes must be handled using:

Alembic

Rules:

no create\_all() in runtime application startup

every schema change must have a migration

migrations must be reviewed before production deployment

migrations must be tested in CI

destructive migrations require explicit approval

rollback strategy must be considered for production changes

migration order must remain clean and reproducible

\---

6.3 Multi-Tenant Data Model

Most tenant-owned tables must include:

tenant\_id

Most site-specific tables must include:

tenant\_id  
site\_id

Examples:

shifts  
availability\_entries  
shift\_requests  
sales\_entries  
hot\_food\_actuals  
hot\_food\_forecasts  
labour\_reports  
notification\_rules  
audit\_logs  
ai\_action\_logs  
exports

Rules:

tenant\_id must be derived from authenticated context

request bodies must not be trusted for tenant\_id

site\_id must be validated against tenant scope

cross-tenant access must return 404 or 403 depending on context

tests must verify tenant isolation for every major module

\---

6.4 Indexing Strategy

Indexes should be added for common query patterns:

tenant\_id  
site\_id  
user\_id  
employee\_account\_id  
created\_at  
week\_start  
status  
subscription\_state

Common compound indexes:

(tenant\_id, site\_id)  
(tenant\_id, site\_id, week\_start)  
(tenant\_id, user\_id)  
(tenant\_id, employee\_account\_id)  
(tenant\_id, site\_id, created\_at)  
(tenant\_id, site\_id, status)

Audit logs may require indexes on:

tenant\_id  
site\_id  
actor\_user\_id  
entity\_type  
entity\_id  
action  
created\_at  
sensitivity\_level

\---

6.5 Soft Delete and Archive Strategy

For operational history, Forecourt\_OS should prefer soft delete/archive instead of hard delete.

Use fields such as:

is\_active  
archived\_at  
deleted\_from\_active\_use\_at  
fully\_erased\_at  
deleted\_by\_user\_id  
archive\_reason

Soft delete applies to:

sites

staff profiles

employee accounts

manual sales entries

hot food entries

request history visibility

rota history visibility

earnings history visibility

AI Help visible history

Hard deletion/full erasure must be restricted and carefully controlled.

\---

6.6 Reporting Data

For MVP, reports can be calculated from operational tables.

Later, reporting may use:

materialized views

reporting tables

analytics warehouse

event streams

scheduled aggregation jobs

MVP should avoid premature data warehouse complexity.

\---

7\. Authentication and Identity

7.1 Authentication Architecture

Forecourt\_OS uses one secure identity system underneath, with separate portal login experiences:

Admin Portal login  
Employee Portal login

Admin-side users:

Owner

Admin

Manager

Employee-side users:

Employee

\---

7.2 Admin-Side Login

Allowed methods:

Google sign-in  
work email \+ password

Applies to:

Owner

Admin

Manager

Admin-side login must support:

email verification

password hashing

forgot password

2FA where required

account lockout or throttling

audit logging

session management

\---

7.3 Employee-Side Login

Allowed method:

site selection first  
username \+ password

Employee login rules:

employees cannot self-register

employees cannot use Google sign-in

employees cannot log in by email in MVP

employee accounts are site-specific

username uniqueness is site-scoped

same real person may have separate credentials per site

employee must authenticate into a selected site context

\---

7.4 Password Storage

Passwords must never be stored in plain text.

Use:

bcrypt  
argon2

Preferred:

argon2id for long-term production  
bcrypt acceptable for current MVP if implemented safely

Password rules:

strong minimum password policy

password confirmation on creation/reset

password hashes only

no password retrieval

reset only, never reveal

employee password reset is Owner-managed unless self-service is enabled later

all reset actions audit logged

\---

7.5 Session and Token Model

Recommended MVP model:

short-lived access tokens  
refresh tokens stored securely  
server-side refresh token tracking

Rules:

access tokens should expire quickly

refresh tokens should be revocable

logout should revoke refresh tokens

suspicious refresh activity should be logged

token secrets must be stored in Secrets Manager

tokens must not contain sensitive data

tokens must not be used as the only source of permission truth

\---

7.6 Two-Factor Authentication

2FA is required for:

Owner login

sensitive actions

payroll access

compliance document access

destructive actions

billing/subscription management

role/permission changes

sensitive audit log access

Recommended MVP approach:

Email OTP first  
Authenticator app/TOTP later

SMS OTP can be added later, but it should not be the only long-term 2FA method.

\---

8\. Role-Based Access Control

8.1 Roles

Forecourt\_OS includes:

Platform Owner / Super Admin  
Owner  
Admin  
Manager  
Employee

\---

8.2 Permission Model

The backend must enforce permissions.

Frontend permission hiding is not enough.

Every protected action must check:

authenticated user  
tenant membership  
role  
site assignment  
specific permission  
sensitive action requirement  
2FA requirement where applicable  
subscription state

\---

8.3 Owner

Owner has highest authority inside the tenant.

Owner can:

manage company profile

manage tenant settings

create Admin accounts

create Manager accounts

create Employee accounts

create/edit sites

configure pay rules

view sensitive employee data

access payroll and compensation

configure notification rules

configure AI permissions

manage billing/subscription

view sensitive audit logs

request tenant suspension/reactivation/erasure

perform destructive actions with confirmation and 2FA

\---

8.4 Admin and Manager

Admins and Managers are operational users.

They may access:

assigned sites only

rota operations

request approvals

reports within scope

hot food module within scope

sales entries within scope

non-sensitive employee profile fields

They cannot:

create accounts

create/edit sites

manage billing

manage tenant-level settings

view compliance documents

view NI-related details

view sensitive audit logs

access payroll unless explicitly granted

perform sensitive governance actions

\---

8.5 Employee

Employees can access only:

their own published rota

their own requests

their own earnings

their own pay-rule breakdown

their own AI Help history

their own visible history

their own exports

currently selected site context

Employees cannot access:

draft rota

co-worker private data

co-worker earnings

co-worker requests

co-worker availability

restricted admin data

payroll administration

compliance documents

tenant settings

billing

sensitive audit logs

\---

9\. Tenant and Site Isolation

9.1 Tenant Isolation Rules

Every tenant-owned record must be protected by tenant scope.

Backend rules:

tenant\_id must come from authenticated context

tenant\_id must not be trusted from request body

tenant\_id must be included in all tenant data queries

tenant\_id must be included in background jobs

tenant\_id must be included in audit logs

tenant\_id must be included in AI action logs

tenant\_id must be included in export metadata

tenant\_id must be used in file storage paths or metadata

\---

9.2 Site Isolation Rules

Site-specific data must be scoped by site.

Backend must check:

Does this site belong to the active tenant?  
Is this user allowed to access this site?  
Does this action require Owner/Admin/Manager/Employee permission?  
Is the subscription state allowing this action?  
Is 2FA required?

\---

9.3 File Isolation

S3 paths should include tenant and site context where appropriate.

Example:

s3://forecourt-os-private/tenants/{tenant\_id}/sites/{site\_id}/documents/{file\_id}  
s3://forecourt-os-private/tenants/{tenant\_id}/exports/{export\_id}  
s3://forecourt-os-private/tenants/{tenant\_id}/audit-exports/{export\_id}

Rules:

no public buckets

no direct open URLs

use short-lived signed URLs

signed URLs generated only after permission check

sensitive files never cached offline

file access must be audit logged where sensitive

\---

9.4 AI Isolation

AI context must be scoped by:

tenant\_id  
site\_id  
user\_id  
role  
permission  
module  
action type

AI must never receive data from:

another tenant

another unauthorised site

another employee’s private data

sensitive documents unless explicitly authorised

billing/security settings unless explicitly allowed for suggestion-only context

\---

10\. Payment and Billing Architecture

10.1 Billing Model

MVP billing model:

base subscription  
extra charge per site  
30-day free trial

Subscription states:

trial  
active  
past\_due  
suspended  
cancelled\_archived  
fully\_erased

\---

10.2 Stripe Billing

Stripe should manage:

subscription plans

recurring invoices

card payment collection

payment method updates

invoice generation

hosted checkout

customer billing portal

webhook events

Forecourt\_OS should manage:

tenant billing state

subscription access control

site count billing quantity

billing event logs

suspension rules

internal access restrictions

owner billing recovery access

\---

10.3 Stripe Data Stored Locally

Forecourt\_OS may store:

stripe\_customer\_id  
stripe\_subscription\_id  
stripe\_price\_id  
stripe\_invoice\_id  
billing\_status  
trial\_start  
trial\_end  
current\_period\_start  
current\_period\_end  
site\_quantity  
last\_payment\_status  
last\_webhook\_event\_id

Forecourt\_OS must not store:

card number  
CVV  
raw payment method details  
full card data  
bank credentials

\---

10.4 Billing Webhooks

Stripe webhooks must be handled securely.

Rules:

verify Stripe webhook signature

reject unverified webhooks

store webhook event ID

make webhook handling idempotent

log webhook processing result

retry safely

do not trust client-side billing state

subscription state changes must be audit logged

Important webhook events may include:

customer.subscription.created  
customer.subscription.updated  
customer.subscription.deleted  
invoice.payment\_succeeded  
invoice.payment\_failed  
checkout.session.completed  
payment\_method.attached

\---

10.5 Suspended Tenant Behaviour

When a tenant is suspended:

Blocked:

operational access

employee portal access

admin/manager access

report exports

AI operational actions

notifications except billing/account recovery where needed

Allowed:

Owner login

billing recovery

subscription reactivation

limited account management

limited read-only historical data if allowed by product policy

\---

11\. Payment Security Rules

Payment security is critical.

Forecourt\_OS must follow these rules:

use Stripe-hosted or Stripe-controlled payment components

never collect raw card data on Forecourt\_OS servers

never store card numbers

never store CVV

never log payment secrets

never expose Stripe secret keys to frontend

verify all payment webhooks

restrict billing management to Owner

require 2FA for billing/subscription changes

audit log billing changes

audit log subscription state changes

audit log payment recovery actions

handle failed payments without exposing sensitive payment details

\---

12\. Data Protection and UK GDPR-Aware Design

12.1 Data Minimisation

Forecourt\_OS must collect only necessary data.

Avoid collecting unnecessary:

personal identifiers

documents

sensitive notes

employee data

location data

free-text sensitive information

\---

12.2 Personal Data Categories

Forecourt\_OS may process:

names

emails

phone numbers

usernames

employee profile data

rota data

availability data

request history

earnings/pay calculation data

right-to-work status

compliance document metadata

uploaded compliance documents where required

audit history

AI Help conversation history

billing contact information

\---

12.3 Sensitive or High-Risk Data

Sensitive areas include:

payroll and compensation

earnings

pay rates

right-to-work documents

NI-related details if collected

identity/compliance documents

sensitive audit logs

billing/subscription management

role and permission changes

destructive actions

These require:

strict RBAC

2FA where applicable

audit logging

encryption

limited access

no offline caching

careful retention rules

\---

12.4 Data Subject Rights Preparation

The platform should be designed to support future handling of:

access requests

correction requests

deletion/erasure requests

export requests

restriction requests

objection requests

MVP does not need fully automated legal workflows, but the data model should not block them.

\---

12.5 Data Retention

Retention rules must be defined for:

tenant data

site data

employee records

payroll calculation history

compliance documents

audit logs

AI Help history

exports

generated reports

billing records

deleted visible history

Current product rule:

cancelled/archived tenant data retained for 90 days

after 90 days, data is not automatically erased

Platform Owner manually executes full erasure

This must be reviewed legally before production launch.

\---

12.6 Offline Cache Rule

Sensitive data must never be available in offline cached mode.

Do not cache offline:

payroll details

compliance documents

NI-related details

sensitive audit logs

billing data

security settings

raw AI prompts containing sensitive data

exported files unless explicitly downloaded by user

\---

13\. File and Document Storage

13.1 Storage Provider

Use:

AWS S3 private buckets

\---

13.2 File Types

Files may include:

right-to-work documents

compliance documents

generated report exports

employee exports

audit exports

AI governance suggestion exports

\---

13.3 File Metadata

PostgreSQL should store file metadata:

id  
tenant\_id  
site\_id  
uploaded\_by\_user\_id  
file\_type  
file\_category  
original\_filename  
storage\_key  
mime\_type  
size\_bytes  
checksum  
created\_at  
deleted\_at  
sensitivity\_level  
access\_policy

\---

13.4 File Access Rules

Files must be accessed through backend permission checks.

Rules:

no public access

no permanent URLs

signed URLs only

short expiry

sensitive access audit logged

download events audit logged

file deletion/archive audit logged

compliance files Owner-only by default

Admin/Manager cannot view compliance document files in MVP

\---

14\. AI Architecture and Safety Boundaries

14.1 AI Architecture

All AI features must go through an internal AI service layer.

Recommended structure:

apps/api/services/ai/  
  ├── client.py  
  ├── prompts/  
  ├── policy.py  
  ├── context\_builder.py  
  ├── safety.py  
  ├── audit.py  
  └── actions.py

The AI service layer must handle:

provider abstraction

prompt construction

permission checks

tenant/site context

action validation

approval requirements

logging

output validation

safety filtering

expiry/invalidated recommendation logic

\---

14.2 AI Data Access Rules

Before sending data to AI, the backend must check:

Who is the user?  
Which tenant are they in?  
Which site are they using?  
What role do they have?  
What module are they using?  
What action are they requesting?  
Are they allowed to see this data?  
Is this sensitive data?  
Is AI allowed to use this data?  
Does the action require confirmation?

\---

14.3 AI Action Categories

AI actions should be classified as:

suggestion\_only  
draft\_generation  
requires\_confirmation  
sensitive\_blocked  
not\_allowed

\---

14.4 AI Allowed Actions

Admin-side AI may assist with:

rota draft generation

rota recommendation explanation

rota recommendation application after confirmation

coverage template draft creation after confirmation

hot food recommendation explanation

sales entry draft creation after confirmation

hot food actual entry draft creation after confirmation

report explanation

report generation

report export after confirmation

notification template suggestions

AI governance/security suggestions for Owner only

Employee AI Help may assist with:

explaining own rota

explaining own requests

explaining own earnings

drafting leave requests

drafting swap requests

drafting cover requests

submitting allowed requests after confirmation

editing/cancelling pending own requests after confirmation

drafting availability updates

exporting own visible data after confirmation

explaining hidden/removed items

restoring own hidden/removed items after confirmation

\---

14.5 AI Not Allowed Actions

AI must not:

publish rota automatically

unpublish rota automatically

approve without confirmation

bypass permissions

access another tenant’s data

access another site without permission

expose co-worker private data

expose payroll admin data to employees

change authentication rules

change 2FA settings

change billing recovery rules

change data retention rules

erase data

perform tenant lifecycle actions

perform site lifecycle actions

perform employee lifecycle actions

reset passwords

access compliance documents unless explicitly authorised by policy

make payment decisions

trigger outbound notifications directly

\---

14.6 AI Audit Logging

Audit logs must record:

AI prompt/action type

user who requested AI action

tenant\_id

site\_id where applicable

module

input context category

output category

whether action was suggestion/draft/executed

confirmation user

confirmation timestamp

whether recommendation became outdated

reversal action where applicable

Do not store raw sensitive prompts unless a clear retention and privacy policy exists.

Prefer storing:

summary

action metadata

decision trail

model/provider used

token usage where useful

safety classification

\---

15\. Notifications Architecture

15.1 MVP Channels

MVP notification channels:

in-product  
SMS  
WhatsApp

Provider:

Twilio

\---

15.2 Notification Rules

Notifications are:

site-specific

role-aware

permission-aware

tenant-scoped

configurable by Owner only

Users receive notifications only for:

assigned sites

allowed event types

allowed role scope

\---

15.3 Notification Events

Examples:

leave request submitted

leave approved/rejected

swap request submitted

cover request submitted

co-worker target accepted/declined

rota published

payroll-sensitive action alert

AI confirmation request

Owner-only AI governance/security suggestion

billing recovery notice

subscription state change

\---

15.4 Notification Safety

Rules:

do not include sensitive payroll details in SMS/WhatsApp

do not include compliance document details in SMS/WhatsApp

do not send AI governance/security suggestions by SMS/WhatsApp

in-product notifications can include richer detail based on permission

notification sending must be logged

failed notification delivery must be tracked

\---

16\. Audit Logging

16.1 Audit Log Purpose

Audit logs provide:

accountability

traceability

security investigation support

compliance support

sensitive access tracking

AI action transparency

destructive action history

\---

16.2 Audit Log Fields

Recommended fields:

id  
tenant\_id  
site\_id  
actor\_user\_id  
actor\_role  
action  
entity\_type  
entity\_id  
before\_value  
after\_value  
metadata  
ip\_address  
user\_agent  
request\_id  
ai\_involved  
sensitivity\_level  
created\_at

\---

16.3 Audit Categories

Audit logs should cover:

auth events

user creation

role changes

site changes

staff profile changes

payroll access

pay rule changes

compliance document access

rota changes

rota publish/unpublish

request approvals/rejections

manual sales entry changes

manual hot food entry changes

AI suggestions

AI confirmations

AI reversals

billing events

exports

destructive actions

notification settings changes

sensitive audit log views

\---

16.4 Sensitive Audit Logs

Sensitive audit logs are Owner-only.

Examples:

payroll access

compliance document access

NI-related access

role/permission changes

destructive actions

billing changes

2FA/security changes

sensitive export downloads

\---

17\. Monitoring and Observability

17.1 Logging

Use structured JSON logs.

Every request should have:

request\_id  
timestamp  
method  
path  
status\_code  
duration\_ms  
user\_id where available  
tenant\_id where available  
site\_id where available

Do not log:

passwords

tokens

raw card data

CVV

full payment method data

sensitive documents

unnecessary personal data

raw sensitive AI prompts

\---

17.2 Error Monitoring

Use:

Sentry  
CloudWatch

Track:

API errors

frontend errors

failed jobs

failed exports

failed webhooks

failed AI calls

failed notification sends

suspicious login patterns

\---

17.3 Metrics

Track:

API latency

database latency

error rate

login failures

rate limit events

webhook failures

export generation time

AI request count

AI failure count

notification delivery failures

subscription state changes

storage usage

background job queue depth

\---

18\. Backup and Disaster Recovery

18.1 Database Backups

Production PostgreSQL must have:

automated backups

point-in-time recovery where available

backup retention policy

restore testing

encrypted backups

access-controlled backup management

\---

18.2 File Backups

S3 storage should use:

versioning where appropriate

lifecycle policies

encryption

restricted access

backup/replication strategy if needed later

\---

18.3 Disaster Recovery Goals

MVP should define realistic targets before production:

RPO: Recovery Point Objective  
RTO: Recovery Time Objective

Suggested MVP targets:

RPO: 24 hours or better  
RTO: 24 hours or better

These can become stricter as the product matures.

\---

18.4 Restore Testing

Backups are not useful unless restore works.

The team must periodically test:

database restore

file restore

migration recovery

accidental deletion recovery

environment rebuild from infrastructure configuration

\---

19\. Deployment and CI/CD

19.1 Environments

Recommended environments:

local  
development  
staging  
production

Production data must never be copied casually into local development.

If production data is needed for debugging, it must be:

anonymised

minimised

approved

access-controlled

\---

19.2 Docker

All backend services should run in Docker.

Docker should be used for:

local development

test execution

API deployment

worker deployment

consistent environment setup

\---

19.3 CI Checks

GitHub Actions should run:

backend tests

frontend tests

linting

type checking

migration checks

Docker build check

security dependency scan

formatting check

\---

19.4 Deployment Rules

Production deployment must:

run migrations safely

use environment secrets

avoid hardcoded credentials

support rollback where possible

require approval for sensitive changes

log deployment events

keep staging close to production

\---

20\. Performance and Scaling

20.1 MVP Performance Stance

The MVP does not require enterprise-scale infrastructure from day one.

However, the architecture must support growth.

Normal actions should feel fast:

login

site switching

loading rota

saving manual sales entries

saving hot food entries

viewing employee portal

viewing reports

exporting standard reports

generating AI recommendations

\---

20.2 Scaling Approach

Scale gradually.

Stage 1: MVP

single API service  
single worker service  
managed PostgreSQL  
Redis  
S3  
Stripe  
Twilio  
OpenAI

Stage 2: Growing Usage

multiple API containers  
multiple workers  
read replicas if needed  
better caching  
background export generation  
queue monitoring

Stage 3: Larger SaaS

analytics warehouse  
event streaming  
separate AI service  
separate reporting service  
multi-region consideration  
advanced observability

\---

20.3 Database Performance

Use:

indexes

pagination

query limits

proper filtering

background jobs for heavy exports

materialized views later if needed

no unbounded tenant-wide queries for normal operational pages

\---

20.4 Export Performance

Exports should be generated asynchronously when heavy.

Export flow:

1\. User requests export.

2\. Backend validates permission.

3\. Export job is queued.

4\. Worker generates file.

5\. File stored in private S3.

6\. User receives in-product notification.

7\. User downloads via short-lived signed URL.

\---

21\. Security Controls

21.1 Core Security Controls

Forecourt\_OS must include:

HTTPS only

secure headers

CORS restrictions

rate limiting

password hashing

strong session management

JWT/refresh token protection

2FA for sensitive areas

tenant isolation

site-scoped access

RBAC

audit logging

secrets management

private file storage

signed URLs

input validation

output encoding

CSRF protection where applicable

SQL injection prevention through ORM and safe query patterns

dependency scanning

error message sanitisation

least privilege cloud IAM

\---

21.2 Secrets Management

Secrets must never be committed to Git.

Use:

AWS Secrets Manager

Secrets include:

database password

JWT secret

Stripe secret key

Stripe webhook secret

Twilio credentials

OpenAI API key

email provider secrets

encryption keys

\---

21.3 Rate Limiting

Rate limiting required for:

login

password reset

OTP verification

AI endpoints

export generation

notification-triggering endpoints

public onboarding endpoints

\---

21.4 Security Headers

Frontend/backend should support:

Content Security Policy

X-Frame-Options or frame-ancestors

X-Content-Type-Options

Referrer-Policy

Strict-Transport-Security

secure cookie settings

\---

21.5 Access to Production

Production access must be limited.

Rules:

least privilege

named user access only

no shared admin accounts

production access logged

database access restricted

S3 access restricted

emergency access documented

developer access reviewed regularly

\---

21.6 Security Testing

Before production launch:

dependency scan

secret scan

authentication tests

RBAC tests

tenant isolation tests

site isolation tests

file access tests

payment webhook tests

AI permission tests

rate-limit tests

export permission tests

sensitive data cache tests

\---

22\. Compliance Documents Needed Before Launch

The technical stack is not enough.

Before public launch, Forecourt\_OS should prepare:

Privacy Policy  
Terms of Service  
Data Processing Agreement  
Cookie Policy  
Subprocessor List  
Data Retention Policy  
Security Overview  
Incident Response Policy  
Access Control Policy  
Acceptable Use Policy  
Backup and Restore Policy  
AI Usage and Safety Policy

\---

22.1 Privacy Policy

Must explain:

what data is collected

why data is collected

how data is used

who data is shared with

retention periods

user rights

contact details

subprocessors

AI processing where applicable

\---

22.2 Data Processing Agreement

Needed because Forecourt\_OS processes employee/customer business data on behalf of tenant businesses.

Should define:

controller/processor roles

processing purpose

subprocessors

security measures

breach notification

deletion/return of data

audit rights

international transfer terms if applicable

\---

22.3 Subprocessor List

Likely subprocessors include:

AWS  
Stripe  
Twilio  
OpenAI  
Sentry  
Vercel if used  
email provider if used

This list must be reviewed before launch.

\---

22.4 Incident Response Policy

Must define:

what counts as an incident

who investigates

how logs are reviewed

customer notification process

regulatory assessment process

containment process

recovery process

post-incident review

\---

23\. MVP vs Later Architecture

23.1 MVP Architecture

MVP includes:

Next.js frontend

FastAPI backend

PostgreSQL

Redis

S3 private storage

Stripe Billing

Twilio SMS/WhatsApp

OpenAI through AI service layer

CloudWatch/Sentry

GitHub Actions

Docker

AWS ECS Fargate

RDS PostgreSQL

Secrets Manager

audit logs

RBAC

tenant isolation

site isolation

2FA for sensitive areas

\---

23.2 Later Enhancements

Later versions may add:

native mobile apps

POS/EPOS integrations

CSV upload

payroll software integrations

analytics warehouse

advanced RAG assistant

richer AI governance engine

full TOTP authenticator 2FA

WebAuthn/passkeys

advanced permission builder

customer-managed retention settings

advanced compliance dashboard

multi-region deployment

enterprise SSO/SAML

SOC 2 readiness

ISO 27001 readiness

formal penetration testing

automated data subject request workflows

\---

24\. Open Technical Decisions

The following decisions should be finalised before production launch.

24.1 Exact AWS Region

Recommended:

eu-west-2

Decision needed:

eu-west-2 or eu-west-1

\---

24.2 Exact Frontend Hosting

Options:

Vercel  
AWS Amplify  
AWS CloudFront/S3  
ECS-hosted frontend

Recommended MVP:

Vercel for speed  
AWS-native later if needed

\---

24.3 Exact 2FA Method

Recommended MVP:

Email OTP

Recommended later:

Authenticator app/TOTP  
WebAuthn/passkeys

\---

24.4 Exact Notification Provider

Recommended MVP:

Twilio

Need confirm:

SMS pricing

WhatsApp approval requirements

sender setup

UK deliverability

message templates

\---

24.5 Exact AI Provider

Recommended MVP:

OpenAI first through internal abstraction layer

Need confirm:

model choice

logging policy

retention policy

whether customer data may be sent to AI provider

customer disclosure language

fallback provider strategy

\---

24.6 Exact Billing Retry Rules

Need define:

failed payment retry count

grace period

when tenant becomes past\_due

when suspension starts

what read-only access remains

how reactivation works

\---

24.7 Exact Data Retention Rules

Need define:

employee records retention

rota history retention

payroll calculation retention

compliance document retention

audit log retention

export file expiry

AI conversation retention

deleted visible history retention

\---

24.8 Exact Security Review Checklist

Need create:

forecourt\_os\_security\_review\_checklist\_v1.md

Should include:

auth checks

RBAC checks

tenant isolation checks

file access checks

AI safety checks

billing security checks

logging checks

backup checks

incident response checks

\---

25\. Technical Architecture Decision Summary

Forecourt\_OS should use the following architecture for MVP:

Frontend:  
Next.js \+ TypeScript \+ Tailwind CSS \+ shadcn/ui

Backend:  
FastAPI \+ Python \+ SQLAlchemy 2.0 \+ Alembic \+ Pytest

Database:  
PostgreSQL

Cache / Jobs:  
Redis \+ Celery or Dramatiq

Cloud:  
AWS

Deployment:  
Docker \+ AWS ECS Fargate

Database Hosting:  
Amazon RDS PostgreSQL

File Storage:  
AWS S3 private buckets

Secrets:  
AWS Secrets Manager

Payments:  
Stripe Billing \+ Stripe Checkout \+ Stripe Webhooks

Notifications:  
Twilio for SMS and WhatsApp

AI:  
OpenAI API through internal AI service layer

Monitoring:  
CloudWatch \+ Sentry

CI/CD:  
GitHub Actions

Security:  
RBAC, tenant isolation, site isolation, 2FA, audit logs, rate limiting, signed URLs, private storage, secrets management

Compliance Direction:  
UK GDPR-aware, privacy-by-design, security-by-design, legal documents required before launch

\---

26\. Final Architecture Rule

Forecourt\_OS must be built as a serious SaaS platform, not as a simple CRUD app.

Every feature must respect:

tenant isolation  
site scope  
role permissions  
sensitive data rules  
audit logging  
AI boundaries  
billing state  
security controls  
data minimisation

If a new feature cannot clearly answer the following questions, it should not be merged:

Who can access this?  
Which tenant does it belong to?  
Which site does it belong to?  
Is this sensitive?  
Does it require 2FA?  
Should it be audit logged?  
Can AI access it?  
Can employees see it?  
Can Admin/Manager see it?  
Can it be exported?  
Can it be cached offline?  
What happens if the tenant is suspended?

\---

27\. Developer and AI Agent Instruction

When building Forecourt\_OS, AI coding agents and developers must follow this document.

Do not introduce:

unscoped tenant queries

hardcoded tenant IDs

hardcoded site IDs

hardcoded secrets

direct public file access

unaudited sensitive actions

AI actions without permission checks

billing logic without webhook verification

employee access to admin data

Admin/Manager access to Owner-only data

frontend-only security

database schema changes without Alembic migrations

production shortcuts that weaken security

All new modules must include:

models

schemas

router/service layer

permission checks

tenant/site isolation

audit logging where applicable

tests

migration if schema changes

clear error handling

documentation update if behaviour changes

\---

28\. End of Document

This document is the first technical architecture PRD for Forecourt\_OS.

It should be updated whenever major technical decisions change.

Recommended next technical documents:

forecourt\_os\_security\_review\_checklist\_v1.md  
forecourt\_os\_database\_schema\_prd\_v1.md  
forecourt\_os\_ai\_architecture\_prd\_v1.md  
forecourt\_os\_billing\_architecture\_prd\_v1.md  
forecourt\_os\_deployment\_runbook\_v1.md  
forecourt\_os\_incident\_response\_policy\_v1.md