"""asset_pipeline -- fetch and generate third-party assets for Otherworld.

Host-side only.  Nothing in this package imports ``unreal``: fetching runs on
the Mac against external APIs, importing runs inside the editor.  The two
halves meet at assets/cache/, which is git-ignored.
"""
