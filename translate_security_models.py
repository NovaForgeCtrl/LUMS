#!/usr/bin/env python3
"""
Translate security model files from English to target languages.
This script identifies English sections and provides translation strings.
"""

import re
import sys

# Translation mappings for common English phrases
TRANSLATIONS = {
    'fi': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMS on tarkoitettu ensisijaisesti hallittuihin infrastruktuuriin, laboratorioihin ja sisäisiin verkkoympäristöihin.\n\nSitä ei saa altistaa suoraan julkiselle Internetille lisäksi suorittamatta turvallisuuskatselmusta ja asianmukaisia verkon valvontaa.',
        
        'Client-side permiso information controls presentation only and never\nreplaces server-side authorization.':
            'Asiakkaan puolen permiso-tieto ohjaa vain esitystä eikä koskaan\nkorvaa palvelimen puolen valtuuttamista.',
    },
    'fr': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMS est destiné principalement aux environnements d\'infrastructure contrôlée, de laboratoire et de réseau interne.\n\nIl ne doit pas être exposé directement à l\'Internet public sans un examen de sécurité supplémentaire et des contrôles réseau appropriés.',
    },
    'ja': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMSは主に制御されたインフラストラクチャ、ラボラトリー、および内部ネットワーク環境を対象としています。\n\n追加のセキュリティレビューと適切なネットワークコントロールなしに、公開インターネットに直接公開してはいけません。',
    },
    'nb': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMS er ment primært for kontrollert infrastruktur, laboratorium- og interne nettverksmiljøer.\n\nDet bør ikke eksponeres direkte til det offentlige Internett uten en ekstra sikkerhetsgjennomgang og passende nettverkskontroller.',
    },
    'pl': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMS jest przeznaczony głównie dla kontrolowanej infrastruktury, laboratorium i wewnętrznych środowisk sieciowych.\n\nNie powinno być narażone bezpośrednio na publiczny Internet bez dodatkowego przeglądu bezpieczeństwa i odpowiednich kontroli sieciowych.',
    },
    'sv': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMS är avsett främst för kontrollerad infrastruktur, laboratorium- och interna nätverksmiljöer.\n\nDet bör inte exponeras direkt mot det offentliga Internet utan en ytterligare säkerhetsgranskning och lämpliga nätverkskontroller.',
    },
    'zh': {
        'LUMS is intended primarily for controlled infrastructure, laboratory, and internal network environments.\n\nIt should not be exposed directly to the public Internet without an additional security review and appropriate network controls.':
            'LUMS 主要用于受控基础设施、实验室和内部网络环境。\n\n未经过额外的安全审查和适当的网络控制，不应直接暴露于公众互联网。',
    }
}

if __name__ == '__main__':
    print("Translation helper for LUMS Security Model files")
    print("This script prints translation patterns for manual editing")
    for lang, translations in TRANSLATIONS.items():
        print(f"\n{lang.upper()}:")
        for english, translated in translations.items():
            print(f"  EN: {english[:50]}...")
            print(f"  TL: {translated[:50]}...")
