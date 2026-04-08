# Special Instructions for Seeding #
Contains instructions on what to keep in mind when generating seed data as certain agents may need data in a certain way to see meaningful output.
Applicable only for tenant_id='tenant-test-001' and bu_id='bu-test-001' which are the FIXED_TENANT/FIXED_BUs.

1. Requirements for WorkerAvailabilityForecastAgent:
- worker_attendance table should have data for last 30 days from today
- worker_roster table should have data for last 30 days from today and also next 15 days from today

