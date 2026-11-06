#!/usr/bin/env python3
"""
Generates realistic sample CV files (.docx, .pdf, .txt) and default vacancy templates.
Includes:
- Outstanding matches (90-96%)
- High matches that miss a mandatory requirement (demonstrating strict disqualification)
- Near-miss matches (85-89%, showing threshold enforcement without lowering)
- Moderate/Junior matches
- Scanned PDF (unreadable text layer requiring OCR / HR review)
- Exact duplicate file with altered name (demonstrating SHA-256 duplicate detection)
"""

import os
import zipfile
import json
import hashlib

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CVS_DIR = os.path.join(DATA_DIR, "sample_cvs")
os.makedirs(CVS_DIR, exist_ok=True)

def create_docx(filepath, text_paragraphs):
    """Creates a genuine, valid Microsoft Word .docx file using zipfile."""
    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    body_xml_parts = []
    for p in text_paragraphs:
        escaped = p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        body_xml_parts.append(f'<w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>')

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        {''.join(body_xml_parts)}
    </w:body>
</w:document>'''

    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as docx:
        docx.writestr('[Content_Types].xml', content_types_xml)
        docx.writestr('_rels/.rels', rels_xml)
        docx.writestr('word/document.xml', document_xml)

def create_simple_pdf(filepath, text):
    """Creates a basic valid PDF text file."""
    # PDF specification minimal stream
    escaped_text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    pdf_content = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        "4 0 obj << /Length " + str(len(escaped_text) + 50) + " >>\n"
        "stream\n"
        "BT /F1 11 Tf 50 750 Td (" + escaped_text[:200] + ") Tj ET\n"
        "BT /F1 10 Tf 50 720 Td (" + escaped_text[200:500] + ") Tj ET\n"
        "BT /F1 10 Tf 50 690 Td (" + escaped_text[500:800] + ") Tj ET\n"
        "endstream\n"
        "endobj\n"
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        "xref\n0 6\n0000000000 65535 f\n"
        "trailer << /Size 6 /Root 1 0 R >>\n"
        "startxref\n500\n%%EOF"
    )
    with open(filepath, "wb") as f:
        f.write(pdf_content.encode('latin1', errors='ignore'))

def create_scanned_unreadable_pdf(filepath):
    """Simulates a scanned raster PDF with no embedded character stream (OCR needed)."""
    # Contains raster stream without font Tj text
    pdf_content = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /XObject << /Im1 5 0 R >> >> >> endobj\n"
        "4 0 obj << /Length 30 >>\n"
        "stream\n"
        "q 600 0 0 780 6 6 cm /Im1 Do Q\n"
        "endstream\n"
        "endobj\n"
        "5 0 obj << /Type /XObject /Subtype /Image /Width 100 /Height 100 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 10 >>\n"
        "stream\n" + ("\x00" * 10) + "\nendstream\n"
        "endobj\n"
        "xref\n0 6\n0000000000 65535 f\n"
        "trailer << /Size 6 /Root 1 0 R >>\n"
        "startxref\n400\n%%EOF"
    )
    with open(filepath, "wb") as f:
        f.write(pdf_content.encode('latin1'))

SAMPLE_CANDIDATES = [
    {
        "filename": "CV_Elena_Vance_Senior_FullStack.docx",
        "format": "docx",
        "lines": [
            "Elena Vance",
            "elena.vance@techhorizon.dev | +1 (555) 234-8901 | San Francisco, CA",
            "Professional Summary: Dedicated Senior Full-Stack Engineer with 8+ years of hands-on experience designing distributed web applications, enterprise microservices, and reactive user interfaces.",
            "Education: Bachelor of Science in Computer Science, University of California Berkeley (Graduated with Honors)",
            "Certifications: AWS Certified Solutions Architect Professional, Certified Kubernetes Application Developer (CKAD)",
            "Mandatory Requirements Compliance: Holds Bachelor Degree in STEM field. 8+ years hands-on production engineering. Full-time right to work verified.",
            "Technical Skills: TypeScript, React, Node.js, Python, PostgreSQL, Docker, Kubernetes, GraphQL, Next.js, Redis, CI/CD, Microservices architecture, Automated Testing (Jest, Playwright).",
            "Work History:",
            "Staff Engineer at NexaFlow Systems (2021 - Present): Lead developer overseeing a core team of 10 engineers building high-throughput event-driven microservices. Spearheaded frontend migration to React and TypeScript, boosting core web vitals by 45%.",
            "Senior Software Engineer at CloudPulse (2018 - 2021): Designed scalable Python and Node.js REST and GraphQL APIs serving 4 million daily requests. Optimized PostgreSQL queries reducing latency by 60%."
        ]
    },
    {
        "filename": "CV_Marcus_Sterling_Principal_Architect.pdf",
        "format": "txt", # Saved as txt for clean test stream
        "lines": [
            "Marcus Sterling",
            "marcus.sterling@devinno.io | +1 (555) 345-6789 | Austin, TX",
            "Summary: Principal Software Architect with 10+ years professional experience architecting mission-critical platforms, cloud-native deployments, and modern web architectures.",
            "Qualifications: Bachelor of Science in Computer Engineering, Georgia Institute of Technology; Master of Science in Software Engineering.",
            "Mandatory Requirements: Over 10 years experience verified. Bachelor degree in STEM. Full work authorization confirmed.",
            "Skills: Python, TypeScript, React, PostgreSQL, Docker, AWS, Distributed Systems, Microservices, System Design, Terraform, Redis, GraphQL, Agile Scrum.",
            "Experience:",
            "Principal Architect at Apex Cloud Solutions (2019 - Present): Led multi-tenant platform redesign with TypeScript, React frontend, and Python backend microservices. Reduced deployment downtime to zero.",
            "Lead Software Engineer at ScalePoint (2015 - 2019): Managed full-stack engineering team, delivered responsive dashboard in React and robust APIs in Python and PostgreSQL."
        ]
    },
    {
        "filename": "CV_Sophia_Chen_Senior_Developer.docx",
        "format": "docx",
        "lines": [
            "Sophia Chen",
            "sophia.chen@innovate.org | +1 (555) 456-7890 | Seattle, WA",
            "Executive Overview: Senior Software Developer with 7 years of engineering experience delivering enterprise web portals, resilient APIs, and responsive web applications.",
            "Education: Bachelor of Science in Information Systems, University of Washington",
            "Certifications: AWS Certified Developer Associate",
            "Mandatory Requirements: 7 years software engineering experience. Bachelor degree confirmed.",
            "Skills: React, TypeScript, Python, Node.js, PostgreSQL, Docker, RESTful APIs, Git, Tailwind CSS, Jest, State Management, Cloud Computing.",
            "Experience:",
            "Senior Frontend & Full Stack Developer at Cascade Health Tech (2020 - Present): Architected customer-facing portals using React and TypeScript. Built data ingestion services using Python and PostgreSQL.",
            "Software Developer at Kinetic Media (2017 - 2020): Developed interactive dashboards and microservices."
        ]
    },
    {
        "filename": "CV_Liam_O_Connor_Lead_Engineer.docx",
        "format": "docx",
        "lines": [
            "Liam O'Connor",
            "liam.oconnor@codeworks.ie | +1 (555) 567-8901 | Boston, MA",
            "Profile: Lead Engineer with 9 years experience building resilient distributed systems, enterprise APIs, and high-performance React frontends.",
            "Education: Bachelor of Science in Computer Science, Trinity College",
            "Mandatory Requirements: 9 years of professional software engineering. Holds accredited Bachelor of Science in Computer Science.",
            "Skills: TypeScript, React, Python, PostgreSQL, Docker, Microservices, CI/CD, AWS, Redis, GraphQL, Next.js, Node.js.",
            "Experience:",
            "Technical Lead at Beacon Analytics (2019 - Present): Spearheaded engineering for analytics dashboards using React, TypeScript, Python, and PostgreSQL.",
            "Senior Full Stack Engineer at Dublin Tech Hub (2015 - 2019): Delivered scalable full-stack applications."
        ]
    },
    {
        "filename": "CV_Alexander_Wright_Disqualified_NoMandatory.docx",
        "format": "docx",
        "lines": [
            "Alexander Wright",
            "alex.wright@digitalcreatives.com | +1 (555) 678-9012 | New York, NY",
            "Profile: Brilliant autodidact frontend developer and UI/UX specialist with 6 years experience in JavaScript, TypeScript, React, HTML5, CSS3, and design systems.",
            "Education: Associate Degree in Graphic Design, City College (Did not attend Bachelor program).",
            "Mandatory Requirements Notice: No Bachelor Degree in STEM field. Only completed 2-year graphic design diploma.",
            "Skills: React, TypeScript, CSS, Node.js, Git, UI/UX, Design Systems, Tailwind CSS, Figma, Frontend Architecture.",
            "Experience: Senior UI Developer at Pulse Studio (2018 - Present): Built UI components in React and TypeScript."
        ]
    },
    {
        "filename": "CV_Jordan_Taylor_Borderline_88Percent.docx",
        "format": "docx",
        "lines": [
            "Jordan Taylor",
            "jordan.taylor@webstack.io | +1 (555) 789-0123 | Chicago, IL",
            "Profile: Full-Stack Developer with 4 years experience. Solid background in web applications.",
            "Education: Bachelor of Science in Computer Science, University of Illinois.",
            "Mandatory Requirements: Bachelor degree verified. 4 years experience (target job requests 6+ years).",
            "Skills: React, JavaScript, Node.js, MongoDB, Git, HTML, CSS. Limited exposure to Python or PostgreSQL.",
            "Experience: Software Engineer at Prairie State Solutions (2020 - Present): Developed web apps using React and Node.js."
        ]
    },
    {
        "filename": "CV_Unreadable_Scanned_Document_Archive.pdf",
        "format": "scanned_pdf",
        "lines": []
    },
    {
        "filename": "CV_Elena_Vance_Duplicate_Submission_v2.docx",
        "format": "docx_duplicate_of_first",
        "lines": []
    }
]

def generate():
    first_file_bytes = None
    for cand in SAMPLE_CANDIDATES:
        filepath = os.path.join(CVS_DIR, cand["filename"])
        if cand["format"] == "docx":
            create_docx(filepath, cand["lines"])
            if first_file_bytes is None:
                with open(filepath, 'rb') as f:
                    first_file_bytes = f.read()
        elif cand["format"] == "docx_duplicate_of_first":
            if first_file_bytes:
                with open(filepath, 'wb') as f:
                    f.write(first_file_bytes)
        elif cand["format"] == "scanned_pdf":
            create_scanned_unreadable_pdf(filepath)
        elif cand["format"] == "txt":
            with open(filepath.replace('.pdf', '.txt'), 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(cand["lines"]))
            # Also create PDF
            create_simple_pdf(filepath, ' '.join(cand["lines"]))
            
    print(f"Generated {len(SAMPLE_CANDIDATES)} sample CV files in {CVS_DIR}")

if __name__ == "__main__":
    generate()
