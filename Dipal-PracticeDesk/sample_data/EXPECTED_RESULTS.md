# Client import expected results

Start in an empty disposable workspace and import clients_demo.csv.

| CSV row | Expected result |
| --- | --- |
| 2 | New: Aravalli Demo LLP |
| 3 | New: Narmada Demo Co |
| 4 | Duplicate of row 2 after name-space/case normalization |
| 5 | Invalid email |

Preview: 2 new, 1 duplicate, 1 invalid. Confirming imports only the two valid new clients. Reimporting after that: 0 new, 3 duplicate, 1 invalid. Existing clients are not overwritten.

All contacts are fictional. example.com addresses are demonstration strings, not destinations for test email. Use Account → Test email to myself.
