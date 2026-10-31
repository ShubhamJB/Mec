# Find Your Mechanic — MVP Team Handoff
Version 1.0 | 30 October 2026

Files:
- Find_Your_Mechanic_SRS_MVP.docx / .md
- Find_Your_Mechanic_ERD_Data_Model.docx / .md
- find_your_mechanic_erd.mmd (editable Mermaid ERD source)
- Find_Your_Mechanic_API_Design.docx / .md
- Find_Your_Mechanic_Frontend_UI_Spec.md (early frontend plan; partly outdated)
- Find_Your_Mechanic_Build_Handoff.md (current state of the build, how to run it, decisions and next steps)

Core ERD: 18 entities. Backend: FastAPI. Frontend: React. Database: PostgreSQL + PostGIS.
API base path: /api/v1.

The Markdown specs include optional, owner-private garage staff CRUD and the implemented roadside assistance backend/first frontend slice. The ERD document records roadside tables and call-check fields; the Mermaid ERD source may still need a diagram refresh. DOCX files are reference copies and may not reflect these Markdown updates.

The API design is a contract baseline; the running backend OpenAPI schema is the route-level reference. Roadside delivery workers, sensitive-data retention controls, and operational safety/support decisions remain pending.
