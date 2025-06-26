# Data Model

This document describes the four tables in the Enviroment Booker application, their columns, data types, constraints, and relationships.

---

## Entity-Relationship Diagram

![ER Diagram of Environment Booker](/docs/images/ERD-diagram.png)

---

## 1. users

Stores all user accounts.

| Column         | Type           | PK? | FK?         | Nullable? | Default      | Description                                   |
| -------------- | -------------- | --- | ----------- | --------- | ------------ | --------------------------------------------- |
| **id**         | `INTEGER`      | ✓   |             | No        |              | Surrogate primary key                         |
| **email**      | `VARCHAR(120)` |     |             | No        |              | Unique user email                             |
| **password_hash** | `VARCHAR(128)` |   |             | No        |              | Hashed password via PBKDF2+SHA256             |
| **role**       | `VARCHAR(20)`  |     |             | No        | `"regular"`  | Either `"regular"` or `"admin"`               |

### Relationships

- **1 → * bookings** (`bookings.user_id` → `users.id`)
- **1 → * audit_log** (`audit_log.actor_id` → `users.id`)

---

## 2. environments

Represents each physical or virtual testing environment.

| Column             | Type           | PK? | FK? | Nullable? | Default                   | Description                                    |
| ------------------ | -------------- | --- | --- | --------- | ------------------------- | ---------------------------------------------- |
| **id**             | `INTEGER`      | ✓   |     | No        |                           | Surrogate primary key                          |
| **name**           | `VARCHAR(100)` |     |     | No        |                           | Unique environment name                        |
| **owner_squad**    | `VARCHAR(50)`  |     |     | No        |                           | Team or squad responsible                      |
| **created_at**     | `DATETIME`     |     |     | No        | `UTC now` (via Python)    | Timestamp when created                         |
| **created_by_email** | `VARCHAR(120)` |   |     | No        |                           | Email of creator (redundant lookup)            |

### Relationships

- **1 → * bookings** (`bookings.environment_id` → `environments.id`)

---

## 3. bookings

Each row is one booked time slot.

| Column           | Type       | PK? | FK?                  | Nullable? | Description                            |
| ---------------- | ---------- | --- | -------------------- | --------- | -------------------------------------- |
| **id**           | `INTEGER`  | ✓   |                      | No        | Surrogate primary key                  |
| **environment_id** | `INTEGER` |     | → `environments.id`  | No        | Which environment is being booked      |
| **user_id**      | `INTEGER`  |     | → `users.id`         | No        | Who made the booking                   |
| **start**        | `DATETIME` |     |                      | No        | Booking start (inclusive)              |
| **end**          | `DATETIME` |     |                      | No        | Booking end (exclusive)                |

### Relationships

- **Many ↔ 1** with **users** and **environments**  

---

## 4. audit_log

Tracks every create/update/delete action.

| Column    | Type       | PK? | FK?              | Nullable? | Default     | Description                                       |
| --------- | ---------- | --- | ---------------- | --------- | ----------- | ------------------------------------------------- |
| **id**    | `INTEGER`  | ✓   |                  | No        |             | Surrogate primary key                             |
| **action**| `VARCHAR(50)` |   |                  | No        |             | e.g. `create_booking`, `delete_environment`       |
| **actor_id** | `INTEGER` |    | → `users.id`     | No        |             | Who performed the action                          |
| **timestamp** | `DATETIME` |  |                  | No        | `utcnow()`  | When it happened                                  |
| **details**  | `TEXT`    |    |                  | Yes       |             | Free-form JSON or human-readable message          |
