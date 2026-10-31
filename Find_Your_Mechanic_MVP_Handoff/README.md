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

The Markdown specs now include optional, owner-private garage staff CRUD. The Mermaid ERD source reflects the additional `garage_staff` entity. Roadside assistance is recorded as a follow-on proposal and is not part of the staff CRUD implementation. DOCX files are reference copies and may not reflect these Markdown updates.

The API design is a contract baseline, not a generated OpenAPI schema. Convert DTO descriptions to Pydantic models and finalize implementation parameters before coding.
