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

ALL = (INTAKE, GENERATE_PACKET, RECORD_FEEDBACK, STATUS)
