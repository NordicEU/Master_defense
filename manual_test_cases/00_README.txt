Manual test cases for the input app
===================================

Use these in the browser at:
http://127.0.0.1:8080

Each file gives you one manual submission to type into the form.

Important note:
- CONTAIN, DECEIVE, and MINEFIELD are manually reachable with the current form.
- HONEYPOT is NOT reliably reachable from the current manual form because the
  decision policy looks for probing-style indicators, and the current manual tax
  form does not produce those signals.

Routing note:
- very high expense-to-income ratios can jump straight to MINEFIELD
- contextual identity mismatch is what most reliably produces DECEIVE
- use the exact values in the files below rather than rough approximations

Recommended reset before testing:
- stop the stack
- clear runtime/
- start the stack again

That way each submission is easier to observe in real time in:
- business app: http://127.0.0.1:8004
- ops app: http://127.0.0.1:8090/ops
