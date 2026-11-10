"""Tool schemas — what the model reads to decide when to call each tool."""

INTAKE = {
    "name": "homework_coach_intake",
    "description": (
        "Analyse photo(s) of a child's completed school homework. Separates printed prompts, the "
        "child's working and answers, skip marks and teacher marks; scores attempted items only; "
        "records skills, task formats and likely slips into that child's learning brief. Use when a "
        "parent shares a homework photo for a child configured in Homework Coach."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "child_id": {"type": "string", "description": "Child id from the family config (e.g. 'nova')."},
            "image_paths": {
                "type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6,
                "description": "Absolute paths to the homework photo(s), in page order.",
            },
            "date": {"type": "string", "description": "Homework date YYYY-MM-DD; defaults to today in the family timezone."},
            "parent_note": {"type": "string", "description": "Optional context from the parent (lesson name, what was assigned)."},
        },
        "required": ["child_id", "image_paths"],
    },
}

GENERATE_PACKET = {
    "name": "homework_coach_generate_packet",
    "description": (
        "Build, verify and render today's practice packet: one printable PDF per child plus a "
        "separate parent answer key. Idempotent per date — a verified same-date packet is reused, "
        "never overwritten. Returns absolute PDF paths and a ready-to-send `message` whose MEDIA: "
        "lines attach the PDFs; reply with that message verbatim when delivering the packet."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Packet date YYYY-MM-DD; defaults to today in the family timezone."},
            "child_ids": {"type": "array", "items": {"type": "string"},
                          "description": "Limit to these children; default is every child scheduled for that date."},
        },
        "required": [],
    },
}

RECORD_FEEDBACK = {
    "name": "homework_coach_record_feedback",
    "description": (
        "Record the parent's per-item feedback on a delivered packet: I = independent, "
        "S = supported, N = not yet. Use when the parent replies to a packet with ratings such as "
        "'nova 1=I 2=S S1=N' (pass the reply text as `reply`), or give child_id + ratings. Defaults "
        "to the child's latest packet. Re-sending the same ratings is safe (no double counting). "
        "Adjusts the next packet's difficulty by at most one dimension per skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reply": {"type": "string",
                      "description": "The parent's reply text, one line per child: '<child> 1=I 2=S S1=N'."},
            "child_id": {"type": "string"},
            "packet_date": {"type": "string", "description": "YYYY-MM-DD of the packet being rated; default latest."},
            "ratings": {"type": "string", "description": "Item ratings, e.g. '1I 2S 3N 4I' or '1=I 2=S'."},
            "note": {"type": "string", "description": "Optional free-text observation."},
        },
        "required": [],
    },
}

STATUS = {
    "name": "homework_coach_status",
    "description": "Show configured children, current classroom anchors, skill levels and recent packets.",
    "parameters": {
        "type": "object",
        "properties": {"child_id": {"type": "string", "description": "Optional: one child only."}},
        "required": [],
    },
}

PROGRESS = {
    "name": "homework_coach_progress",
    "description": (
        "Parent progress report: what each child is working on in class (from the latest homework "
        "photo), how many practice days were rated, the share of items done on their own now vs the "
        "previous window, and per-skill trends and difficulty changes. Use when the parent asks how a "
        "child is doing, whether practice matches class, or for a weekly check-in. Reply with the "
        "result's `message` field."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "child_id": {"type": "string", "description": "Optional: one child only."},
            "days": {"type": "integer", "description": "Window length in days (default 14).", "minimum": 3, "maximum": 90},
        },
        "required": [],
    },
}

_UNIT = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Unit name as the school calls it, e.g. 'Topic 3: Multiplication facts'."},
        "skill": {"type": "string", "enum": ["count", "place_value", "add_sub", "multiplication", "division", "fractions"],
                  "description": "Closest practice skill. Omit if none fits (unit is recorded but not practised)."},
        "start": {"type": "string", "description": "YYYY-MM-DD (best estimate from the pacing guide)."},
        "end": {"type": "string", "description": "YYYY-MM-DD."},
        "goals": {"type": "array", "items": {"type": "string"}, "description": "What students should be able to do by the end."},
        "standards": {"type": "array", "items": {"type": "string"}, "description": "Standard codes, e.g. 3.OA.A.1."},
        "vocabulary": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["title", "start", "end"],
}

SET_CURRICULUM = {
    "name": "homework_coach_set_curriculum",
    "description": (
        "Preload a child's school-year curriculum plan so packets follow class even between homework "
        "photos. FIRST research the curriculum yourself (web search the district's pacing guide / scope "
        "and sequence and the publisher program named in the child's config, plus the grade standards), "
        "then call this with the units in order, their approximate dates, goals and standards, and the "
        "source URLs. A recent homework photo still outranks the plan. Re-call to correct dates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "child_id": {"type": "string"},
            "curriculum": {"type": "string", "description": "Program name, e.g. 'Savvas enVision Mathematics Grade 3'."},
            "school_year": {"type": "string", "description": "e.g. 2026-27"},
            "units": {"type": "array", "items": _UNIT, "minItems": 1},
            "sources": {"type": "array", "items": {"type": "string"}, "description": "URLs or document names the plan came from."},
            "replace": {"type": "boolean", "description": "Replace the whole plan (default true); false merges units."},
        },
        "required": ["child_id", "units", "sources"],
    },
}

ADD_MATERIAL = {
    "name": "homework_coach_add_material",
    "description": (
        "Save teacher material for a child (newsletter, unit overview, study guide, practice page, "
        "or a typed note) and what it says the class is working on. Read the file first (vision for "
        "images/PDF pages), then pass the skill it targets, the goals it states and a one-line "
        "summary. Materials refine the goals that steer packets; they are kept locally."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "child_id": {"type": "string"},
            "path": {"type": "string", "description": "Local file path (pdf, image, txt, md, docx). Omit for a typed note."},
            "title": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD the material is from (default today)."},
            "kind": {"type": "string", "description": "newsletter | unit overview | study guide | worksheet | note"},
            "skill": {"type": "string", "enum": ["count", "place_value", "add_sub", "multiplication", "division", "fractions"]},
            "goals": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
        },
        "required": ["child_id", "title"],
    },
}

ALL = (INTAKE, GENERATE_PACKET, RECORD_FEEDBACK, STATUS, PROGRESS, SET_CURRICULUM, ADD_MATERIAL)
