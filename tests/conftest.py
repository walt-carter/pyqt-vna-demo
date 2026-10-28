import os

# Run Qt without a display so GUI tests behave the same in Emacs, terminals, and CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
