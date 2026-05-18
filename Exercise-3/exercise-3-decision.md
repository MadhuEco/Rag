# Exercise 3  Decision Document
## Teams Bot with Entra ID SSO and RAG over SharePoint


## 1. Problem

Food & Beverage colleagues (~8,000 SharePoint documents  SOPs, safety data sheets, playbooks) cannot find answers through SharePoint search alone. They need a Microsoft Teams bot that:

- Authenticates via **Entra ID SSO** (no additional login)
- Answers natural-language questions with source citations
- **Never** surfaces a chunk from a document outside the user's SharePoint ACL
- Supports multi-turn follow-ups
- Runs entirely within the Ecolab EU Azure tenant

---

## 2. Options Considered

### Variant A  Azure-Native, Hand-Built
Bot Framework Web App on Azure App Service + Azure OpenAI + Azure AI Search (SharePoint indexer + ACL trimming via OBO token) + Cosmos DB for conversation state. All resources in West Europe, behind a Virtual Network with Private Endpoints.

### Variant B Microsoft Copilot Studio Declarative Agent
Declarative agent configured in Copilot Studio, grounded on SharePoint via Microsoft Graph Connector and the M365 Copilot Semantic Index, published to Teams. No custom infrastructure; everything managed within the M365 EU tenant.

---

## 3. Trade-off Scorecard

| Axis | Variant A (Azure-Native) | Variant B (Copilot Studio) |

| **Time-to-first-user** | **Medium** ~610 weeks (Bot Framework + AI Search setup, OBO flow, infra) | **High** ~2-4 weeks (GUI config, no custom infra) |
| **Permission fidelity** | **High**  OBO delegated token passed to AI Search at query time; ACL trimming explicit and auditable | **High**  Graph Connector inherits SharePoint permissions natively; M365 Copilot enforces them |
| **Data residency** | **High** all resources locked to West Europe; Private Endpoints prevent public egress | **High**  M365 EU tenant; data never leaves region (assuming EU Copilot deployment) |
| **Cost per active user/month** | **Medium**  ~47/user/month at 10 queries/day (App Service S2, AI Search S1, AOAI pay-per-use, Cosmos). Scales linearly with queries, not seats | **Low-to-High**  ~$0 extra if M365 Copilot licenses already exist; ~2530/user/month if new seats needed. Licensing cost dominates at scale |
| **Extensibility** | **High**  custom Tool Dispatcher can call SAP, Snowflake, any API; agentic retrieval straightforward to add | **Low**  limited to Power Platform connectors; calling internal APIs requires premium licensing and a custom connector; no agentic retrieval today |
| **Vendor lock-in** | **Medium**  locked to Azure PaaS but code is portable; migrating LLM or search is possible | **High** deeply tied to M365 Copilot roadmap; feature availability, pricing, and LLM choice controlled by Microsoft |
| **Observability** | **High**  App Insights traces every pipeline step; structured logs for retrieval, ACL filter, and completion | **Low**  Copilot Studio analytics gives aggregate metrics; no per-query trace of why an answer was generated |
| **Skills required** | **High**  needs Python/Node developer, Azure architect, Bot Framework knowledge | **Low**  Power Platform admin / Copilot Studio configurator sufficient |



## 4. Winner: Variant A Azure-Native

### Rationale

The decisive axes are **extensibility** and **observability**.

The Food & Beverage BU has already signalled future requirements to call SAP for product data and Snowflake for audit results. Variant B cannot support these without significant licensing uplift and is architecturally closed to agentic retrieval patterns. Once we hit the first "add a tool" request, Copilot Studio becomes a blocker, not an accelerator.

Observability is equally critical. Colleagues will ask questions that touch regulatory content (safety data sheets). When a wrong or missing answer appears, an engineer must be able to explain why  which chunk was retrieved, which ACL filter excluded a document, which completion was generated. Copilot Studio offers none of this; Variant A exposes every step through App Insights.

Permission fidelity is equivalent between variants: both enforce ACL at retrieval time. Data residency is equivalent: both stay in EU. These are not differentiators.

The cost argument favours Variant B only if M365 Copilot E3/E5 licenses already cover the user population. At 500 users with existing licensing, Variant B is cheaper. At 40,000 users without existing licenses (~1.2M/year in new Copilot seats), Variant A is decisively cheaper. We model the 40,000-user expansion scenario as likely within 18 months.

### What Variant A sacrifices

- **Time-to-first-user**: 4-6 weeks longer than Variant B. This is the real cost.
- **Skills required**: we need at least one developer comfortable with Bot Framework and Azure PaaS. If that person is unavailable, we revisit.
- **Operational ownership**: on-call for App Service, AI Search, Cosmos DB. Variant B has zero infra on-call.

### What would change our minds

- If Microsoft announces GA of agentic Copilot Studio connectors for arbitrary APIs before our pilot deadline revisit extensibility.
- If the BU confirms the 40,000-user expansion is off the table and all users already hold M365 Copilot licenses  cost model inverts; revisit Variant B.
- If the platform team confirms no developer capacity for the next 3 months  accept Variant B as a time-boxed interim.



## 5. Responses to Twists

| Twist | Variant A response | Changes winner? |

| "No content may leave the EU tenant" | All resources already in West Europe behind Private Endpoints. AI Search indexer reads SharePoint via Graph API within tenant. No change required. | No |
| "500  40,000 users" | App Service scales horizontally (autoscale rules); AI Search scales replicas; Cosmos DB is serverless. Stress-test the OBO token acquisition path (concurrency limit). | No strengthens A |
| "BU wants to add SAP tool" | Add a new Tool in the Tool Dispatcher; register it with the Orchestrator. ~1 sprint. | No |
| "Multi-document comparison questions" | Add agentic retrieval (multi-hop) to the Orchestrator loop. RAG still works with query decomposition. | No |
| "Budget cap 5,000/month all-in" | At 500 users: App Service S2 (~180) + AI Search S1 (~250) + Cosmos (~50) + AOAI (~1,500 at 10 queries/user/day) **2,000/month**. Comfortably under cap. | No |


## 6. Architecture Decision Records (ADRs)

### ADR-01: OBO Token for ACL Trimming
**Decision:** Use On-Behalf-Of flow to obtain a delegated token per request, passed to Azure AI Search for ACL-trimmed results.  
**Rationale:** Guarantees that the search index only returns documents the calling user can open. App-level service principal search would require replicating SharePoint permissions into the index  fragile and laggy.  
**Trade-off accepted:** OBO adds ~50-100 ms per request and requires the bot registration to have `Sites.Read.All` delegated scope.  
**We will know we were wrong when:** Latency SLA cannot be met at peak load due to token acquisition overhead  at which point we evaluate token caching with short TTLs.

### ADR-02: Azure AI Search over pgvector
**Decision:** Use Azure AI Search (managed) rather than self-hosted pgvector.  
**Rationale:** AI Search has a native SharePoint Online indexer and built-in ACL field filtering. pgvector requires building and maintaining the indexer pipeline ourselves.  
**Trade-off accepted:** Higher cost per query than pgvector; tied to Azure Search pricing.  
**We will know we were wrong when:** AI Search pricing exceeds pgvector total cost of ownership at our query volume estimate break-even at ~50M queries/month.

### ADR-03: Cosmos DB for Conversation State
**Decision:** Cosmos DB NoSQL API with per-user partition key for conversation history.  
**Rationale:** Horizontally scalable, low-latency reads, available in West Europe, TTL-based expiry for privacy compliance.  
**Trade-off accepted:** Cost at scale (serverless Cosmos is not free above ~100M RU/month). Alternative: Azure Table Storage is cheaper but no server-side TTL.  
**We will know we were wrong when:** Cosmos cost line exceeds 500/month at which point evaluate Azure Redis Cache for hot session state.
