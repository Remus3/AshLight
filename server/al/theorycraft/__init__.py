"""Theorycraft layer (decision 0004): Path of Building PoE2 file interop.

Phase C is stdlib only: `codec` turns a PoB2 share code into build XML and
back, `model` reads the XML into a typed, read-only view, `store` keeps the
last loaded build across restarts. Format knowledge comes from research 0010
section 1 (PoB2 is MIT; no PoB code is copied here).
"""
