#!/usr/bin/env python3
import os
import re

def generate_translations():
    # Read source file
    with open('./troubleshooting.md', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Define all translations
    translations = {
        'de': {
            'LUMS Troubleshooting': 'LUMS Fehlerbehebung',
            'Getting Started: Troubleshoot Safely': 'Erste Schritte: Sichere Fehlerbehebung',
            'If you are new to Linux, an error does not automatically mean that data has\nbeen lost': 'Wenn Sie neu in Linux sind, bedeutet ein Fehler nicht automatisch, dass Daten\nverloren gegangen sind',
            'Do not change several things at once': 'Ändern Sie nicht mehrere Dinge auf einmal',
            'First checks on the LUMS server': 'Erste Überprüfungen auf dem LUMS-Server',
            'First checks on a managed client': 'Erste Überprüfungen auf einem verwalteten Client',
            'Before sharing command output': 'Vor dem Teilen der Befehlsausgabe',
            'Troubleshooting Philosophy': 'Fehlerbehebungsphilosophie',
            'Diagnostic Baseline': 'Diagnostische Grundlage',
            'First Diagnostic Checks': 'Erste diagnostische Überprüfungen',
            'Check the LUMS Container': 'Überprüfen Sie den LUMS-Container',
            'Check Recent Application Logs': 'Überprüfen Sie die aktuellen Anwendungsprotokolle',
            'Check Nginx': 'Überprüfen Sie Nginx',
            'Check the Agent': 'Überprüfen Sie den Agent',
            'Check the Execution Watcher': 'Überprüfen Sie den Ausführungs-Watcher',
            'Check LUMS Timers': 'Überprüfen Sie LUMS-Timer',
        },
        'en-GB': {},  # No translation for British English (same as source)
    }
    
    print("Translation dictionary created")
    print(f"Source length: {len(source)}")
    print(f"German translations: {len(translations['de'])}")

if __name__ == '__main__':
    generate_translations()
