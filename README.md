# Admission Robot AI Brain

Standalone Python AI Brain for the ECU Admission Robot.

## Current version

This version includes the complete Text Intelligence Layer:

- text normalization
- Arabic letter normalization
- Arabic/Persian digit normalization
- spoken digit sequence normalization
- protected entity extraction
- faculty detection
- intent detection
- search query construction

## Run

```bash
python main.py
```

## Useful commands inside the runner

```text
lang ar
lang en
mode qa
mode registration
exit
```

## Test examples

```text
my email is test@example.com and my phone is 010 1234 5678 and my grade is 92.5% in 2024
```

```text
lang ar
عايز اعرف مصاريف هندسة كام
```
