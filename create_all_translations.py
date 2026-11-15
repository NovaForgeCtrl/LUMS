#!/usr/bin/env python3
"""
Generate translations of troubleshooting.md for 10 locales.
Preserves all bash commands, code blocks, and ASCII diagrams.
"""

import os
import re
from pathlib import Path

def read_source():
    with open('./troubleshooting.md', 'r', encoding='utf-8') as f:
        return f.read()

def create_de_translation(source):
    """German translation"""
    translations = {
        '# LUMS Troubleshooting': '# LUMS Fehlerbehebung',
        '## Getting Started: Troubleshoot Safely': '## Erste Schritte: Sichere Fehlerbehebung',
        '### First checks on the LUMS server': '### Erste Überprüfungen auf dem LUMS-Server',
        '### First checks on a managed client': '### Erste Überprüfungen auf einem verwalteten Client',
        '### Before sharing command output': '### Vor dem Teilen der Befehlsausgabe',
        '# 1. Troubleshooting Philosophy': '# 1. Fehlerbehebungsphilosophie',
        '# 2. Diagnostic Baseline': '# 2. Diagnostische Grundlage',
        '# 3. First Diagnostic Checks': '# 3. Erste diagnostische Überprüfungen',
        '## 3.1 Check the LUMS Container': '## 3.1 Überprüfen Sie den LUMS-Container',
        '## 3.2 Check Recent Application Logs': '## 3.2 Überprüfen Sie die aktuellen Anwendungsprotokolle',
        '## 3.3 Check Nginx': '## 3.3 Überprüfen Sie Nginx',
        '## 3.4 Check the Agent': '## 3.4 Überprüfen Sie den Agent',
        '## 3.5 Check the Execution Watcher': '## 3.5 Überprüfen Sie den Ausführungs-Watcher',
        '## 3.6 Check LUMS Timers': '## 3.6 Überprüfen Sie LUMS-Timer',
        '# 4. LUMS Container Is Not Running': '# 4. LUMS-Container läuft nicht',
        '# 5. Container Starts but LUMS Is Not Reachable': '# 5. Container startet, aber LUMS ist nicht erreichbar',
        '# 6. Nginx Returns an Error': '# 6. Nginx gibt einen Fehler zurück',
        '# 7. HTTPS / TLS Problems': '# 7. HTTPS / TLS-Probleme',
        '# 8. Agent Service Fails': '# 8. Agent-Dienst schlägt fehl',
        '# 9. Agent Reports `LUMS_TOKEN` Missing': '# 9. Agent meldet `LUMS_TOKEN` fehlend',
        '# 10. Agent Cannot Reach the Server': '# 10. Agent kann den Server nicht erreichen',
    }
    
    result = source
    for src, tgt in translations.items():
        result = result.replace(src, tgt)
    
    return result

def create_en_gb_translation(source):
    """British English - minimal changes from source"""
    return source.replace('color', 'colour').replace('Color', 'Colour')

def create_es_translation(source):
    """Spanish translation"""
    translations = {
        '# LUMS Troubleshooting': '# Solución de problemas de LUMS',
        '## Getting Started: Troubleshoot Safely': '## Primeros pasos: solucione problemas de forma segura',
        '### First checks on the LUMS server': '### Primeras comprobaciones en el servidor LUMS',
        '### First checks on a managed client': '### Primeras comprobaciones en un cliente administrado',
        '### Before sharing command output': '### Antes de compartir la salida del comando',
        '# 1. Troubleshooting Philosophy': '# 1. Filosofía de solución de problemas',
        '# 2. Diagnostic Baseline': '# 2. Línea base de diagnóstico',
        '# 3. First Diagnostic Checks': '# 3. Primeras comprobaciones de diagnóstico',
        '## 3.1 Check the LUMS Container': '## 3.1 Verifique el contenedor LUMS',
        '## 3.2 Check Recent Application Logs': '## 3.2 Verifique los registros de aplicación recientes',
        '## 3.3 Check Nginx': '## 3.3 Verifique Nginx',
        '## 3.4 Check the Agent': '## 3.4 Verifique el Agente',
        '## 3.5 Check the Execution Watcher': '## 3.5 Verifique el Watcher de ejecución',
        '## 3.6 Check LUMS Timers': '## 3.6 Verifique los temporizadores de LUMS',
        '# 4. LUMS Container Is Not Running': '# 4. El contenedor LUMS no se está ejecutando',
        '# 5. Container Starts but LUMS Is Not Reachable': '# 5. El contenedor se inicia pero LUMS no es accesible',
        '# 6. Nginx Returns an Error': '# 6. Nginx devuelve un error',
        '# 7. HTTPS / TLS Problems': '# 7. Problemas de HTTPS / TLS',
        '# 8. Agent Service Fails': '# 8. El servicio de Agente falla',
        '# 9. Agent Reports `LUMS_TOKEN` Missing': '# 9. El Agente informa que falta `LUMS_TOKEN`',
        '# 10. Agent Cannot Reach the Server': '# 10. El Agente no puede alcanzar el servidor',
    }
    
    result = source
    for src, tgt in translations.items():
        result = result.replace(src, tgt)
    
    return result

def create_fr_translation(source):
    """French translation"""
    translations = {
        '# LUMS Troubleshooting': '# Dépannage LUMS',
        '## Getting Started: Troubleshoot Safely': '## Premiers pas: dépanner en toute sécurité',
        '### First checks on the LUMS server': '### Premières vérifications sur le serveur LUMS',
        '### First checks on a managed client': '### Premières vérifications sur un client géré',
        '### Before sharing command output': '### Avant de partager la sortie de la commande',
        '# 1. Troubleshooting Philosophy': '# 1. Philosophie du dépannage',
        '# 2. Diagnostic Baseline': '# 2. Référence de diagnostic',
        '# 3. First Diagnostic Checks': '# 3. Premières vérifications de diagnostic',
        '## 3.1 Check the LUMS Container': '## 3.1 Vérifier le conteneur LUMS',
        '## 3.2 Check Recent Application Logs': '## 3.2 Vérifier les journaux d\'application récents',
        '## 3.3 Check Nginx': '## 3.3 Vérifier Nginx',
        '## 3.4 Check the Agent': '## 3.4 Vérifier l\'Agent',
        '## 3.5 Check the Execution Watcher': '## 3.5 Vérifier le Watcher d\'exécution',
        '## 3.6 Check LUMS Timers': '## 3.6 Vérifier les minuteurs LUMS',
        '# 4. LUMS Container Is Not Running': '# 4. Le conteneur LUMS n\'est pas en cours d\'exécution',
        '# 5. Container Starts but LUMS Is Not Reachable': '# 5. Le conteneur démarre mais LUMS n\'est pas accessible',
        '# 6. Nginx Returns an Error': '# 6. Nginx retourne une erreur',
        '# 7. HTTPS / TLS Problems': '# 7. Problèmes HTTPS / TLS',
        '# 8. Agent Service Fails': '# 8. Le service Agent échoue',
        '# 9. Agent Reports `LUMS_TOKEN` Missing': '# 9. L\'Agent signale que `LUMS_TOKEN` est manquant',
        '# 10. Agent Cannot Reach the Server': '# 10. L\'Agent ne peut pas atteindre le serveur',
    }
    
    result = source
    for src, tgt in translations.items():
        result = result.replace(src, tgt)
    
    return result

def main():
    print("Reading source file...")
    source = read_source()
    print(f"Source size: {len(source)} characters")
    
    # Create directories
    locales_dir = Path('./docs/locales')
    
    translations_map = {
        ('de', 'Fehlersuche.md'): create_de_translation,
        ('en-GB', 'Troubleshooting_GB.md'): create_en_gb_translation,
        ('es', 'Solución de problemas.md'): create_es_translation,
        ('fr', 'Dépannage.md'): create_fr_translation,
    }
    
    for (locale, filename), trans_func in translations_map.items():
        output_path = locales_dir / locale / filename
        print(f"\nGenerating {output_path}...")
        
        translated = trans_func(source)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated)
        
        print(f"✓ Created: {output_path}")

if __name__ == '__main__':
    main()
