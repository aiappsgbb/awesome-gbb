"""Contract for an additive link: never redeclare a shared zone or VNet."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "skills/azd-patterns/references/bicep/private-dns-vnet-link.bicep"


class PrivateDnsLinkTests(unittest.TestCase):
    def test_only_link_is_created_in_existing_zone(self):
        self.assertTrue(MODULE.is_file(), "Canonical private DNS link module is missing")
        text = MODULE.read_text()
        self.assertIn("privateDnsZones@2020-06-01' existing", text)
        self.assertIn("privateDnsZones/virtualNetworkLinks@2020-06-01", text)
        self.assertIn("registrationEnabled: false", text)
        self.assertIn("id: virtualNetworkId", text)
        self.assertNotIn("NxDomainRedirect", text)
        self.assertNotIn("virtualNetworks@", text)
        self.assertIn("output id string = link.id", text)

    def test_private_aca_modules_preserve_network_and_identity_boundaries(self):
        expected = {
            "aca-environment.bicep": ("internal: true", "workloadProfileType: 'Consumption'", "workspaceId: logAnalyticsWorkspaceId"),
            "aca-subnet.bicep": ("virtualNetworks@2024-05-01' existing", "serviceName: 'Microsoft.App/environments'", "id: natGatewayId"),
            "uami.bicep": ("Microsoft.ManagedIdentity/userAssignedIdentities@", "output principalId string"),
            "acr-pull.bicep": ("registries@2023-07-01' existing", "7f951dda-4ed3-4680-a7ca-43fe172d538d", "principalType: 'ServicePrincipal'"),
            "aca-private-dns.bicep": ("registrationEnabled: false", "ipv4Address: staticIp", "output linkIds array"),
        }
        for name, fragments in expected.items():
            with self.subTest(module=name):
                path = MODULE.parent / name
                self.assertTrue(path.is_file(), f"Canonical module missing: {name}")
                text = path.read_text()
                for fragment in fragments:
                    self.assertIn(fragment, text)
                self.assertNotIn("SecurityControl", text)
                self.assertNotIn("NxDomainRedirect", text)


if __name__ == "__main__":
    unittest.main()
