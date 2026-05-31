import json

with open('test_e2e.txt') as f:
    d = json.load(f)
cc = d['contract_c']

print('=== GENERATED CODE ===')
for m in cc['generated_code']:
    print(f'  {m["filename"]}: {m["description"]}')
    print(f'  Lines: {m["source_code"].count(chr(10))+1}')

print()
print('=== QUALITY REPORT ===')
qr = cc.get('quality_report')
if qr:
    print(f'  Avg CC: {qr["avg_cyclomatic_complexity"]}')
    print(f'  Maintainability: {qr["maintainability_index_avg"]}')
    print(f'  Issues: {len(qr["issues"])}')
    for iss in qr['issues']:
        print(f'    [{iss["severity"]}] {iss["tool"]}: {iss["message"][:60]}')

print()
print('=== TRACEABILITY MATRIX ===')
tm = cc.get('traceability_matrix')
if tm:
    for row in tm:
        print(f'  {row["scenario_id"]} => {row["module"]} (tests: {row["test_count"]})')

print()
print('=== COVERAGE REPORT ===')
cr = cc.get('coverage_report')
if cr:
    print(f'  Line: {cr["line_coverage_pct"]}% | Branch: {cr["branch_coverage_pct"]}%')

print()
print('=== REVIEW ===')
r = cc['review']
print(f'  Status: {r["review_status"]}')
print(f'  Version: {r["version"]}')

print()
print('=== OUTPUT FILE ===')
print(f'  {d.get("output_file", "N/A")}')
