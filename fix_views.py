import codecs

f = 'teams/views.py'
raw = open(f, 'rb').read()
try:
    # First, let's decode it as utf-8 (which gives the corrupted text containing Â¡, Ã³, etc.)
    text = raw.decode('utf-8')
    # Now, let's encode it back as latin-1 to get the correct raw bytes, and decode as utf-8
    fixed = text.encode('latin-1').decode('utf-8')
    # Save it back
    open(f, 'wb').write(fixed.encode('utf-8'))
    print("SUCCESS: Fixed views.py encoding!")
except Exception as e:
    print("FAILED:", str(e))
