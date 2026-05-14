# Exercise 1 — Buying Coffee with a Contactless Card at a Café

## System Description

This model describes the end-to-end process of a customer buying coffee at a café
using a contactless payment card. The system spans three layers — Business,
Application, and Technology — showing how a simple everyday transaction involves
people, software, and physical hardware working together.

---

## Business Layer

The two main actors are the **Customer** and the **Barista**. The Customer initiates
the interaction by placing an order. This triggers three interconnected business
processes: **Orders coffee**, **Payment**, and **Preparing and serving coffee**.

The Customer is assigned to the Orders coffee and Payment processes — they are the
person placing the order and paying for it. The Barista is assigned to the Preparing
and serving coffee process — they physically make and hand over the coffee.

Three business services support these processes:
- **Coffee ordering service** serves the Orders coffee process — it is the capability
  the café offers to let customers place orders.
- **Payment Service** serves the Payment process — it is the capability to accept
  and process card payments.
- **Coffee Preparation** serves the Preparing and serving coffee process — it is the
  capability to make the coffee once an order is confirmed.

Two business objects exist in this layer:
- **Coffee order** — the record of what the customer has asked for, which flows
  through the ordering process.
- **Payment Receipt** — the proof of transaction that is produced after payment
  is completed.

---

## Application Layer

The application layer contains the software systems that make the business services
possible.

Two application components power the system:
- **POS Application** — the Point-of-Sale software running on the counter terminal.
  It realizes the Order Processing and Inventory Lookup services.
- **Payment Gateway** — the software that handles payment authorization. It realizes
  the Payment Authorization service.

Three application services are exposed by these components:
- **Order Processing** — handles the customer's order and serves the Orders coffee
  business process.
- **Payment Authorization** — validates and approves the card payment, serving the
  Payment business process.
- **Inventory Lookup Service** — checks stock availability, serving the Preparing
  and serving coffee process.

One data object exists in this layer:
- **Transaction Data** — the digital record of the payment transaction, which flows
  upward to produce the Payment Receipt in the business layer.

---

## Technology Layer

The technology layer contains the physical devices and infrastructure that the
application layer runs on.

Three devices are present:
- **POS Terminal** — the physical counter terminal that hosts the POS Application
  and connects to the Network Connectivity service.
- **Card Reader** — the hardware device that reads the customer's contactless card
  and serves the Payment Authorization process directly.
- **Application Server** — the server that hosts and runs the POS Application and
  Payment Gateway components.

Two technology services support the application layer:
- **Network Connectivity** — provides the network connection that Order Processing
  depends on to function.
- **Payment Network Service** — the external card network (e.g. Visa/Mastercard)
  that Payment Authorization depends on to approve transactions.

The **Payment Server (Bank)** is the bank-side system software that realizes the
Payment Network Service — it is the actual backend that approves or declines the
card transaction.

---

## How the Layers Connect

A customer taps their card on the Card Reader. The Card Reader serves the Payment
Authorization application service running on the Payment Gateway component, which
is hosted on the Application Server. The Payment Gateway connects via the Payment
Network Service to the bank's Payment Server to approve the transaction. Meanwhile,
the POS Application running on the POS Terminal processes the order through the
Network Connectivity service. Once the transaction is approved, Transaction Data
flows up to produce a Payment Receipt, and the Barista prepares and serves the
coffee.
