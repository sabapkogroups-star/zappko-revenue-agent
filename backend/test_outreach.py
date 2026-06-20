from audit import audit_website
from outreach import generate_outreach

audit = audit_website(
    "https://www.zappko.com"
)

result = generate_outreach(
    "Zappko",
    audit
)

print(result["email"])
print()
print(result["whatsapp"])