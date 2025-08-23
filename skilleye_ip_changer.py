#!/usr/bin/env python3
"""
Interactive Menu-Driven ONVIF Camera IP Changer
Automatically discovers cameras in network and provides easy menu interface
"""

import requests
import logging
import json
import os
import getpass
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
import ipaddress
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket

class Camera:
    def __init__(self, ip: str, name: str = "", model: str = "", manufacturer: str = ""):
        self.ip = ip
        self.name = name or f"Camera-{ip}"
        self.model = model
        self.manufacturer = manufacturer
        self.reachable = True
        
    def __str__(self):
        return f"{self.name} ({self.ip})" + (f" - {self.manufacturer} {self.model}" if self.model else "")

class ONVIFIPChanger:
    def __init__(self):
        self.setup_logging()
        self.config = self.load_config()
        self.cameras: List[Camera] = []
        self.current_network = ""
        self.credentials = {"username": "", "password": ""}
        
    def setup_logging(self):
        """Configure logging system"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"ip_change_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Script started - Log saved to: {log_filename}")
    
    def load_config(self) -> dict:
        """Load configuration from JSON file if exists"""
        config_file = "camera_config.json"
        default_config = {
            "username": "admin",
            "password": "",
            "timeout": 5,
            "scan_ports": [80, 8080, 8081, 554, 8554],
            "scan_threads": 50
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.logger.info("Configuration loaded from file")
                    return {**default_config, **config}
            except Exception as e:
                self.logger.warning(f"Error loading config: {e}")
        
        return default_config
    
    def validate_network(self, network: str) -> bool:
        """Validate network CIDR format"""
        try:
            ipaddress.IPv4Network(network, strict=False)
            return True
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            return False
    
    def manage_dhcp_settings(self, camera: Camera) -> bool:
        """Manage DHCP settings for selected camera"""
        print(f"\n🔧 DHCP Management for: {camera}")
        print(f"Current IP: {camera.ip}")
        
        # Get current network configuration
        print(f"🔍 Getting current DHCP status...")
        current_config = self.get_current_network_config(camera.ip, self.credentials["username"], self.credentials["password"])
        
        current_dhcp = current_config["dhcp_enabled"]
        current_addresses = current_config["addresses"]
        
        print(f"   Current DHCP: {'✅ Enabled' if current_dhcp else '❌ Disabled'}")
        if current_addresses:
            print(f"   Current IPs: {current_addresses}")
        
        # Show DHCP options
        print(f"\n📋 DHCP OPTIONS:")
        print(f"1. Enable DHCP (automatic IP assignment)")
        print(f"2. Disable DHCP (manual/static IP mode)")
        print(f"3. View detailed network info")
        print(f"0. Cancel")
        
        choice = input(f"\nEnter your choice: ").strip()
        
        if choice == '1':
            return self.set_dhcp_mode(camera.ip, True)
        elif choice == '2':
            return self.set_dhcp_mode(camera.ip, False)
        elif choice == '3':
            self.show_detailed_network_info(camera.ip)
            return False
        else:
            print("❌ Operation cancelled")
            return False
    
    def set_dhcp_mode(self, ip: str, enable_dhcp: bool) -> bool:
        """Enable or disable DHCP on camera"""
        mode_str = "ENABLE" if enable_dhcp else "DISABLE"
        print(f"\n🚀 Attempting to {mode_str} DHCP...")
        
        # Get current interface info
        current_config = self.get_current_network_config(ip, self.credentials["username"], self.credentials["password"])
        interfaces = self.get_network_interfaces(ip, self.credentials["username"], self.credentials["password"])
        interface_token = interfaces[0] if interfaces else "eth0"
        
        print(f"   Using interface: {interface_token}")
        print(f"   Target: {'Enable' if enable_dhcp else 'Disable'} DHCP")
        
        # Confirm action
        confirm = input(f"\nProceed to {mode_str} DHCP? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Operation cancelled")
            return False
        
        url = f"http://{ip}/onvif/device_service"
        
        # Create SOAP request for DHCP change
        soap_body = f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
          <s:Header/>
          <s:Body>
            <tds:SetNetworkInterfaces>
              <tds:InterfaceToken>{interface_token}</tds:InterfaceToken>
              <tds:NetworkInterface>
                <tt:Enabled>true</tt:Enabled>
                <tt:Info>
                  <tt:Name>{interface_token}</tt:Name>
                  <tt:MTU>1500</tt:MTU>
                </tt:Info>
                <tt:IPv4>
                  <tt:Enabled>true</tt:Enabled>
                  <tt:Config>
                    <tt:DHCP>{str(enable_dhcp).lower()}</tt:DHCP>
                  </tt:Config>
                </tt:IPv4>
                <tt:IPv6><tt:Enabled>false</tt:Enabled></tt:IPv6>
              </tds:NetworkInterface>
            </tds:SetNetworkInterfaces>
          </s:Body>
        </s:Envelope>'''
        
        # Log the request
        self.logger.info(f"DHCP {mode_str} SOAP Request:\n{soap_body}")
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body, 
                headers=headers,
                auth=(self.credentials["username"], self.credentials["password"]),
                timeout=self.config.get('timeout', 15)
            )
            
            self.logger.info(f"DHCP {mode_str} - HTTP Status: {response.status_code}")
            self.logger.info(f"DHCP {mode_str} Response:\n{response.text}")
            
            print(f"\n📋 DHCP {mode_str} RESPONSE:")
            print("-" * 50)
            print(response.text)
            print("-" * 50)
            
            if response.status_code == 200:
                response_text = response.text
                has_success = "SetNetworkInterfacesResponse" in response_text and "RebootNeeded" in response_text
                
                if has_success:
                    print(f"✅ ONVIF command sent successfully")
                    
                    # Check if reboot is needed
                    reboot_needed = "rebootneeded>true" in response_text.lower() or "rebootneeded=\"true\"" in response_text.lower()
                    if reboot_needed:
                        print("   ⚠️  Camera may need reboot for changes to take effect")
                    else:
                        print("   ℹ️  No reboot required")
                    
                    # Wait and verify the change
                    print(f"\n🕐 Waiting for DHCP change to take effect...")
                    time.sleep(5)
                    
                    # Check if DHCP setting actually changed
                    print(f"🔍 Verifying DHCP setting change...")
                    new_config = self.get_current_network_config(ip, self.credentials["username"], self.credentials["password"])
                    
                    if new_config["dhcp_enabled"] == enable_dhcp:
                        print(f"✅ DHCP setting successfully changed!")
                        print(f"   DHCP is now: {'✅ Enabled' if enable_dhcp else '❌ Disabled'}")
                        
                        if new_config["addresses"]:
                            print(f"   Current IP addresses: {new_config['addresses']}")
                            
                        if enable_dhcp:
                            print(f"\n💡 Camera should now obtain IP automatically from DHCP server")
                            print(f"   You may need to check your router/DHCP server for the new IP")
                        else:
                            print(f"\n💡 Camera is now in static IP mode")
                            print(f"   You can now try setting a manual IP address")
                        
                        return True
                    else:
                        current_dhcp_str = "enabled" if new_config["dhcp_enabled"] else "disabled"
                        print(f"❌ DHCP setting did not change (still {current_dhcp_str})")
                        return False
                else:
                    print(f"❌ ONVIF command rejected")
                    return False
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"❌ Connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Unable to connect to camera")
            return False
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False
    
    def show_detailed_network_info(self, ip: str) -> None:
        """Show comprehensive network information"""
        print(f"\n📊 DETAILED NETWORK INFORMATION")
        print("="*60)
        
        current_config = self.get_current_network_config(ip, self.credentials["username"], self.credentials["password"])
        
        print(f"IP Address: {ip}")
        
        if current_config["addresses"]:
            print(f"Reported IP addresses: {current_config['addresses']}")
        
        if current_config["interface_tokens"]:
            print(f"Interface tokens: {current_config['interface_tokens']}")
        
        print(f"DHCP enabled: {'✅ Yes' if current_config['dhcp_enabled'] else '❌ No'}")
        
        if current_config["prefix_lengths"]:
            print(f"Prefix lengths: {current_config['prefix_lengths']}")
        
        if current_config["full_response"]:
            print(f"\nFull GetNetworkInterfaces Response:")
            print("-" * 60)
            # Pretty print the XML
            import re
            formatted_xml = current_config["full_response"]
            # Add some basic formatting
            formatted_xml = re.sub(r'><', '>\n<', formatted_xml)
            print(formatted_xml)
            print("-" * 60)
    
    def try_alternative_with_linklocal_preserved(self, old_ip: str, new_ip: str, gateway: str, prefix_length: int, interface_token: str, hw_address: str) -> bool:
        """Try alternative approach preserving LinkLocal and including HwAddress"""
        url = f"http://{old_ip}/onvif/device_service"
        
        # Some cameras expect LinkLocal to remain as auto-generated (169.254.x.x)
        # and get upset if you try to change it
        soap_body_alt = f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
          <s:Header/>
          <s:Body>
            <tds:SetNetworkInterfaces>
              <tds:InterfaceToken>{interface_token}</tds:InterfaceToken>
              <tds:NetworkInterface>
                <tt:Enabled>true</tt:Enabled>'''
        
        # Include HwAddress if we found it
        if hw_address:
            soap_body_alt += f'''
                <tt:Info>
                  <tt:Name>{interface_token}</tt:Name>
                  <tt:HwAddress>{hw_address}</tt:HwAddress>
                  <tt:MTU>1500</tt:MTU>
                </tt:Info>'''
        else:
            soap_body_alt += f'''
                <tt:Info>
                  <tt:Name>{interface_token}</tt:Name>
                  <tt:MTU>1500</tt:MTU>
                </tt:Info>'''
        
        soap_body_alt += f'''
                <tt:IPv4>
                  <tt:Enabled>true</tt:Enabled>
                  <tt:Config>
                    <tt:Manual>
                      <tt:Address>{new_ip}</tt:Address>
                      <tt:PrefixLength>{prefix_length}</tt:PrefixLength>
                    </tt:Manual>
                    <tt:DHCP>false</tt:DHCP>
                  </tt:Config>
                </tt:IPv4>
                <tt:IPv6><tt:Enabled>false</tt:Enabled></tt:IPv6>
              </tds:NetworkInterface>
              <tds:IPv4Gateway>
                <tt:Address>{gateway}</tt:Address>
              </tds:IPv4Gateway>
            </tds:SetNetworkInterfaces>
          </s:Body>
        </s:Envelope>'''
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body_alt, 
                headers=headers,
                auth=(self.credentials["username"], self.credentials["password"]),
                timeout=self.config.get('timeout', 10)
            )
            
            self.logger.info(f"LinkLocal preserved format - HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                response_text = response.text
                has_onvif_success = "SetNetworkInterfacesResponse" in response_text and "RebootNeeded" in response_text
                
                if has_onvif_success:
                    print(f"      ✅ LinkLocal preserved format accepted")
                    return True
                else:
                    print(f"      ❌ LinkLocal preserved format rejected")
            
        except Exception as e:
            self.logger.warning(f"LinkLocal preserved format error: {e}")
        
        return False
    
    def disable_dhcp_first(self, ip: str, interface_token: str) -> bool:
        """Try to disable DHCP first, as some cameras require this"""
        url = f"http://{ip}/onvif/device_service"
        
        soap_body = f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
          <s:Header/>
          <s:Body>
            <tds:SetNetworkInterfaces>
              <tds:InterfaceToken>{interface_token}</tds:InterfaceToken>
              <tds:NetworkInterface>
                <tt:Enabled>true</tt:Enabled>
                <tt:IPv4>
                  <tt:Enabled>true</tt:Enabled>
                  <tt:DHCP>false</tt:DHCP>
                </tt:IPv4>
              </tds:NetworkInterface>
            </tds:SetNetworkInterfaces>
          </s:Body>
        </s:Envelope>'''
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body, 
                headers=headers,
                auth=(self.credentials["username"], self.credentials["password"]),
                timeout=self.config.get('timeout', 10)
            )
            
            return response.status_code == 200 and "SetNetworkInterfacesResponse" in response.text
            
        except Exception as e:
            self.logger.warning(f"DHCP disable error: {e}")
        
        return False
    
    def validate_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ipaddress.AddressValueError:
            return False
    
    def get_network_range(self) -> str:
        """Get network range from user"""
        while True:
            print("\n" + "="*50)
            print("NETWORK CONFIGURATION")
            print("="*50)
            
            if self.current_network:
                network = input(f"Enter network range [{self.current_network}]: ").strip()
                if not network:
                    network = self.current_network
            else:
                network = input("Enter network range (e.g., 192.168.1.0/24): ").strip()
            
            if self.validate_network(network):
                self.current_network = network
                return network
            else:
                print("❌ Invalid network format. Use CIDR notation (e.g., 192.168.1.0/24)")
    
    def check_onvif_port(self, ip: str, port: int, timeout: float) -> bool:
        """Check if ONVIF service is available on IP:port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def get_camera_info(self, ip: str, username: str, password: str) -> Optional[Camera]:
        """Get camera information via ONVIF"""
        url = f"http://{ip}/onvif/device_service"
        
        soap_body = '''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
          <s:Header/>
          <s:Body>
            <tds:GetDeviceInformation/>
          </s:Body>
        </s:Envelope>'''
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body, 
                headers=headers,
                auth=(username, password),
                timeout=self.config.get('timeout', 5)
            )
            
            if response.status_code == 200:
                # Extract basic info (simplified parsing)
                content = response.text
                manufacturer = ""
                model = ""
                
                if "Manufacturer>" in content:
                    manufacturer = content.split("Manufacturer>")[1].split("<")[0]
                if "Model>" in content:
                    model = content.split("Model>")[1].split("<")[0]
                
                return Camera(ip, f"Camera-{ip}", model, manufacturer)
            
        except:
            pass
        
        return None
    
    def get_network_interfaces(self, ip: str, username: str, password: str) -> List[str]:
        """Get available network interface tokens"""
        url = f"http://{ip}/onvif/device_service"
        
        soap_body = '''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
          <s:Header/>
          <s:Body>
            <tds:GetNetworkInterfaces/>
          </s:Body>
        </s:Envelope>'''
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body, 
                headers=headers,
                auth=(username, password),
                timeout=self.config.get('timeout', 10)
            )
            
            if response.status_code == 200:
                # Extract interface tokens
                content = response.text
                interfaces = []
                
                # Look for interface tokens in response
                import re
                tokens = re.findall(r'<tt:token>([^<]+)</tt:token>', content)
                interfaces.extend(tokens)
                
                # Fallback patterns
                if not interfaces:
                    tokens = re.findall(r'token="([^"]+)"', content)
                    interfaces.extend(tokens)
                
                self.logger.info(f"Found network interfaces: {interfaces}")
                return interfaces if interfaces else ["eth0"]
            
        except Exception as e:
            self.logger.warning(f"Error getting network interfaces: {e}")
        
        return ["eth0"]  # Default fallback
    
    def try_alternative_ip_change(self, old_ip: str, new_ip: str, gateway: str, prefix_length: int, interface_token: str) -> bool:
        """Try alternative SOAP formats for IP change"""
        url = f"http://{old_ip}/onvif/device_service"
        
        # Alternative SOAP format - some cameras prefer different structures
        soap_body_alt = f'''<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
          <soap:Header/>
          <soap:Body>
            <tds:SetNetworkInterfaces>
              <tds:InterfaceToken>{interface_token}</tds:InterfaceToken>
              <tds:NetworkInterface>
                <tt:Enabled>true</tt:Enabled>
                <tt:Link>
                  <tt:AutoNegotiation>true</tt:AutoNegotiation>
                  <tt:Speed>100</tt:Speed>
                  <tt:Duplex>Full</tt:Duplex>
                </tt:Link>
                <tt:MTU>1500</tt:MTU>
                <tt:IPv4>
                  <tt:Enabled>true</tt:Enabled>
                  <tt:Config>
                    <tt:Manual>
                      <tt:Address>{new_ip}</tt:Address>
                      <tt:PrefixLength>{prefix_length}</tt:PrefixLength>
                    </tt:Manual>
                    <tt:DHCP>false</tt:DHCP>
                  </tt:Config>
                </tt:IPv4>
              </tds:NetworkInterface>
              <tds:IPv4Gateway>
                <tt:Address>{gateway}</tt:Address>
              </tds:IPv4Gateway>
            </tds:SetNetworkInterfaces>
          </soap:Body>
        </soap:Envelope>'''
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body_alt, 
                headers=headers,
                auth=(self.credentials["username"], self.credentials["password"]),
                timeout=self.config.get('timeout', 10)
            )
            
            self.logger.info(f"Alternative format - HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                response_text = response.text
                has_onvif_success = "SetNetworkInterfacesResponse" in response_text and "RebootNeeded" in response_text
                
                if has_onvif_success:
                    print(f"      ✅ Alternative format accepted")
                    return True
                else:
                    print(f"      ❌ Alternative format rejected")
            
        except Exception as e:
            self.logger.warning(f"Alternative format error: {e}")
        
        return False
    
    def scan_network_for_cameras(self, network: str) -> List[Camera]:
        """Scan network range for ONVIF cameras"""
        cameras = []
        network_obj = ipaddress.IPv4Network(network, strict=False)
        ports = self.config.get('scan_ports', [80, 8080])
        max_threads = self.config.get('scan_threads', 50)
        
        print(f"\n🔍 Scanning network {network} for ONVIF cameras...")
        print(f"   Ports: {ports}")
        print(f"   IPs to scan: {network_obj.num_addresses}")
        print("   This may take a moment...\n")
        
        # First pass: find IPs with open ports
        open_ips = []
        
        def check_ip_ports(ip_str):
            ip_obj = ipaddress.IPv4Address(ip_str)
            if ip_obj == network_obj.network_address or ip_obj == network_obj.broadcast_address:
                return None
                
            for port in ports:
                if self.check_onvif_port(ip_str, port, 1.0):
                    return ip_str
            return None
        
        # Scan IPs in parallel
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_ip = {executor.submit(check_ip_ports, str(ip)): str(ip) 
                           for ip in network_obj.hosts()}
            
            completed = 0
            for future in as_completed(future_to_ip):
                completed += 1
                if completed % 50 == 0:
                    print(f"   Scanned {completed}/{network_obj.num_addresses-2} IPs...")
                
                result = future.result()
                if result:
                    open_ips.append(result)
        
        print(f"   Found {len(open_ips)} IPs with open ports")
        
        # Second pass: check ONVIF services
        if open_ips:
            print("   Checking ONVIF services...")
            
            for ip in open_ips:
                print(f"   Testing {ip}...", end=" ")
                
                # Try without auth first
                camera = self.get_camera_info(ip, "", "")
                
                # Try with credentials if available
                if not camera and self.credentials["username"]:
                    camera = self.get_camera_info(ip, self.credentials["username"], self.credentials["password"])
                
                if not camera:
                    # Create basic camera entry even if we can't get full info
                    camera = Camera(ip)
                
                cameras.append(camera)
                print("✅ ONVIF camera found")
        
        return cameras
    
    def get_credentials(self) -> None:
        """Get and store user credentials"""
        print("\n" + "="*30)
        print("CAMERA CREDENTIALS")
        print("="*30)
        
        default_user = self.config.get('username', 'admin')
        username = input(f"Username [{default_user}]: ").strip()
        if not username:
            username = default_user
        
        password = getpass.getpass("Password: ")
        
        self.credentials = {"username": username, "password": password}
    
    def display_cameras(self) -> None:
        """Display list of discovered cameras"""
        print("\n" + "="*60)
        print("DISCOVERED CAMERAS")
        print("="*60)
        
        if not self.cameras:
            print("❌ No cameras found")
            return
        
        print(f"Network: {self.current_network}")
        print(f"Found: {len(self.cameras)} camera(s)\n")
        
        for i, camera in enumerate(self.cameras, 1):
            status = "🟢" if camera.reachable else "🔴"
            print(f"  [{i:2d}] {status} {camera}")
    
    def show_main_menu(self) -> str:
        """Display main menu and get user choice"""
        print("\n" + "="*40)
        print("MAIN MENU")
        print("="*40)
        print("1. Scan for cameras")
        print("2. Refresh camera list")
        print("3. Change camera IP")
        print("4. Set/Remove DHCP")
        print("5. Show camera details")
        print("6. Set credentials")
        print("7. Change network")
        print("0. Exit")
        print("-" * 40)
        
        choice = input("Enter your choice: ").strip()
        return choice
    
    def change_camera_ip(self, camera: Camera) -> bool:
        """Change IP of selected camera"""
        print(f"\n📝 Changing IP for: {camera}")
        print(f"Current IP: {camera.ip}")
        
        # Get new IP
        while True:
            new_ip = input("Enter new IP address: ").strip()
            if not new_ip:
                print("❌ Operation cancelled")
                return False
            
            if not self.validate_ip(new_ip):
                print("❌ Invalid IP address format")
                continue
                
            if new_ip == camera.ip:
                print("❌ New IP is same as current IP")
                continue
                
            break
        
        # Get network settings - auto-detect gateway from current network
        network_obj = ipaddress.IPv4Network(self.current_network, strict=False)
        default_gateway = str(network_obj.network_address + 1)  # Usually .1 in the network
        
        gateway = input(f"Gateway [{default_gateway}]: ").strip() or default_gateway
        if not self.validate_ip(gateway):
            print("❌ Invalid gateway, using default")
            gateway = default_gateway
        
        prefix_length = input("Prefix length [24]: ").strip() or "24"
        try:
            prefix_length = int(prefix_length)
            if not (8 <= prefix_length <= 30):
                prefix_length = 24
        except:
            prefix_length = 24
        
        # Validate network configuration
        try:
            new_ip_obj = ipaddress.IPv4Address(new_ip)
            gateway_obj = ipaddress.IPv4Address(gateway)
            network_obj = ipaddress.IPv4Network(f"{new_ip}/{prefix_length}", strict=False)
            
            if gateway_obj not in network_obj:
                print(f"⚠️  WARNING: Gateway {gateway} is not in the same network as {new_ip}/{prefix_length}")
                print(f"   This may cause connectivity issues")
                confirm = input("   Continue anyway? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    print("❌ Operation cancelled")
                    return False
        except:
            pass
        
        # Confirm
        print(f"\n⚠️  CONFIRMATION")
        print(f"Camera: {camera}")
        print(f"Change: {camera.ip} → {new_ip}")
        print(f"Gateway: {gateway}/{prefix_length}")
        
        confirm = input("\nProceed? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Operation cancelled")
            return False
        
        # Perform the change
        return self.execute_ip_change(camera.ip, new_ip, gateway, prefix_length)
    
    def verify_ip_change(self, new_ip: str, timeout: int = 30) -> bool:
        """Verify that camera is accessible at new IP"""
        print(f"🔍 Verifying camera is accessible at {new_ip}...")
        
        for attempt in range(timeout):
            try:
                # Try to connect to new IP
                if self.check_onvif_port(new_ip, 80, 2.0):
                    # Try ONVIF call to new IP
                    test_camera = self.get_camera_info(new_ip, self.credentials["username"], self.credentials["password"])
                    if test_camera:
                        print(f"✅ Camera successfully accessible at {new_ip}")
                        return True
                
                if attempt < 5:  # Only show progress for first few attempts
                    print(f"   Attempt {attempt + 1}/{timeout}... waiting")
                elif attempt == 5:
                    print(f"   Still trying... (this may take up to {timeout} seconds)")
                
                time.sleep(1)
                
            except Exception as e:
                if attempt == 0:
                    self.logger.warning(f"Verification error: {e}")
        
        print(f"❌ Camera not accessible at {new_ip} after {timeout} seconds")
        return False
    
    def get_current_network_config(self, ip: str, username: str, password: str) -> dict:
        """Get current network configuration from camera"""
        url = f"http://{ip}/onvif/device_service"
        
        soap_body = '''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
          <s:Header/>
          <s:Body>
            <tds:GetNetworkInterfaces/>
          </s:Body>
        </s:Envelope>'''
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            response = requests.post(
                url, 
                data=soap_body, 
                headers=headers,
                auth=(username, password),
                timeout=self.config.get('timeout', 10)
            )
            
            if response.status_code == 200:
                content = response.text
                
                # Parse current IP addresses and more details
                import re
                addresses = re.findall(r'<tt:Address>([0-9.]+)</tt:Address>', content)
                
                # Extract interface tokens with more patterns
                interface_tokens = []
                
                # Pattern 1: Standard ONVIF token attribute
                tokens1 = re.findall(r'<[^>]*token="([^"]+)"[^>]*>', content)
                interface_tokens.extend(tokens1)
                
                # Pattern 2: Token in element content
                tokens2 = re.findall(r'<[^>]*[Tt]oken[^>]*>([^<]+)</[^>]*[Tt]oken[^>]*>', content)
                interface_tokens.extend(tokens2)
                
                # Pattern 3: Interface name patterns
                tokens3 = re.findall(r'<[^>]*[Nn]ame[^>]*>([^<]+)</[^>]*[Nn]ame[^>]*>', content)
                interface_tokens.extend(tokens3)
                
                # Remove duplicates
                interface_tokens = list(set(interface_tokens))
                
                # Parse DHCP status
                dhcp_enabled = "dhcp>true" in content.lower() or "dhcp=\"true\"" in content.lower()
                
                # Parse prefix length
                prefix_lengths = re.findall(r'<tt:PrefixLength>([0-9]+)</tt:PrefixLength>', content)
                
                return {
                    "addresses": addresses,
                    "interface_tokens": interface_tokens,
                    "dhcp_enabled": dhcp_enabled,
                    "prefix_lengths": prefix_lengths,
                    "full_response": content
                }
            
        except Exception as e:
            self.logger.warning(f"Error getting current network config: {e}")
        
        return {
            "addresses": [], 
            "interface_tokens": [],
            "dhcp_enabled": False,
            "prefix_lengths": [],
            "full_response": ""
        }

    def execute_ip_change(self, old_ip: str, new_ip: str, gateway: str, prefix_length: int) -> bool:
        """Execute the actual IP change via ONVIF with comprehensive debugging"""
        url = f"http://{old_ip}/onvif/device_service"
        self.logger.info(f"Changing IP: {old_ip} -> {new_ip}")
        
        # Step 0: Get current network configuration for debugging
        print(f"🔍 Getting current network configuration...")
        current_config = self.get_current_network_config(old_ip, self.credentials["username"], self.credentials["password"])
        
        if current_config["addresses"]:
            print(f"   Current IP addresses: {current_config['addresses']}")
        if current_config["interface_tokens"]:
            print(f"   Found interface tokens: {current_config['interface_tokens']}")
        if current_config["prefix_lengths"]:
            print(f"   Current prefix lengths: {current_config['prefix_lengths']}")
        print(f"   DHCP enabled: {current_config['dhcp_enabled']}")
        
        # Show the complete GetNetworkInterfaces response for debugging
        if current_config["full_response"]:
            print(f"\n📋 CURRENT NETWORK CONFIGURATION:")
            print("-" * 60)
            print(current_config["full_response"])
            print("-" * 60)
        
        # Step 1: Get available network interfaces
        print(f"\n🔍 Getting network interfaces from separate call...")
        interfaces = self.get_network_interfaces(old_ip, self.credentials["username"], self.credentials["password"])
        
        # Combine all possible interface tokens
        all_tokens = list(set(interfaces + current_config["interface_tokens"]))
        if not all_tokens:
            all_tokens = ["eth0"]  # fallback
        
        print(f"   All discovered interface tokens: {all_tokens}")
        interface_token = all_tokens[0]
        print(f"   Using interface: {interface_token}")
        
        # Step 1.5: Try to disable DHCP first if it's enabled
        if current_config["dhcp_enabled"]:
            print(f"\n🔧 DHCP is currently enabled, trying to disable it first...")
            if self.disable_dhcp_first(old_ip, interface_token):
                print(f"   ✅ DHCP disable command sent")
                time.sleep(2)  # Wait for DHCP to be disabled
            else:
                print(f"   ⚠️  DHCP disable failed, continuing anyway")
        else:
            print(f"   ℹ️  DHCP is already disabled")
        
        soap_body = f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
          <s:Header/>
          <s:Body>
            <tds:SetNetworkInterfaces>
              <tds:InterfaceToken>{interface_token}</tds:InterfaceToken>
              <tds:NetworkInterface>
                <tt:Enabled>true</tt:Enabled>
                <tt:Info>
                  <tt:Name>{interface_token}</tt:Name>
                  <tt:MTU>1500</tt:MTU>
                </tt:Info>
                <tt:IPv4>
                  <tt:Enabled>true</tt:Enabled>
                  <tt:Config>
                    <tt:Manual>
                      <tt:Address>{new_ip}</tt:Address>
                      <tt:PrefixLength>{prefix_length}</tt:PrefixLength>
                    </tt:Manual>
                    <tt:LinkLocal>
                      <tt:Address>{new_ip}</tt:Address>
                      <tt:PrefixLength>{prefix_length}</tt:PrefixLength>
                    </tt:LinkLocal>
                    <tt:DHCP>false</tt:DHCP>
                  </tt:Config>
                </tt:IPv4>
                <tt:IPv6><tt:Enabled>false</tt:Enabled></tt:IPv6>
              </tds:NetworkInterface>
              <tds:IPv4Gateway>
                <tt:Address>{gateway}</tt:Address>
              </tds:IPv4Gateway>
            </tds:SetNetworkInterfaces>
          </s:Body>
        </s:Envelope>'''
        
        # Log the exact SOAP request being sent
        self.logger.info(f"SOAP Request Body:\n{soap_body}")
        
        try:
            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": ""
            }
            
            print(f"\n🚀 Sending IP change command...")
            print(f"   Target: {old_ip} → {new_ip}")
            print(f"   Gateway: {gateway}/{prefix_length}")
            print(f"   Interface: {interface_token}")
            
            response = requests.post(
                url, 
                data=soap_body, 
                headers=headers,
                auth=(self.credentials["username"], self.credentials["password"]),
                timeout=self.config.get('timeout', 15)
            )
            
            self.logger.info(f"HTTP Status: {response.status_code}")
            self.logger.info(f"Full Response:\n{response.text}")
            
            # Show complete response for debugging
            print(f"\n📋 COMPLETE SOAP RESPONSE:")
            print("-" * 60)
            print(response.text)
            print("-" * 60)
            
            if response.status_code == 200:
                response_text = response.text
                response_lower = response_text.lower()
                
                # Check for SOAP faults first
                if "soap:fault" in response_lower or "s:fault" in response_lower or "fault" in response_lower:
                    print("❌ SOAP Fault detected in response")
                    
                    # Extract fault information
                    import re
                    fault_codes = re.findall(r'<[^>]*faultcode[^>]*>([^<]+)</[^>]*faultcode[^>]*>', response_text, re.IGNORECASE)
                    fault_strings = re.findall(r'<[^>]*faultstring[^>]*>([^<]+)</[^>]*faultstring[^>]*>', response_text, re.IGNORECASE)
                    
                    if fault_codes:
                        print(f"   Fault Code: {fault_codes[0]}")
                    if fault_strings:
                        print(f"   Fault String: {fault_strings[0]}")
                    
                    return False
                
                # Look for more comprehensive success/failure indicators
                success_patterns = [
                    r'<[^>]*SetNetworkInterfacesResponse',
                    r'<ns8:SetNetworkInterfacesResponse',
                    r'<tds:SetNetworkInterfacesResponse',
                    r'RebootNeeded'
                ]
                
                # More specific failure patterns to avoid false positives
                failure_patterns = [
                    r'<[^>]*[Ff]ault[^>]*>',  # SOAP fault elements
                    r'>[^<]*[Ee]rror[^<]*<',  # Error in element content
                    r'>[^<]*[Uu]nauthorized[^<]*<',  # Unauthorized in content
                    r'>[^<]*[Ff]orbidden[^<]*<',  # Forbidden in content
                    r'>[^<]*[Ii]nvalid[^<]*<'  # Invalid in content
                ]
                
                # Check for success patterns
                import re
                has_success = any(re.search(pattern, response_text, re.IGNORECASE) for pattern in success_patterns)
                has_failure = any(re.search(pattern, response_text, re.IGNORECASE) for pattern in failure_patterns)
                
                print(f"\n🔍 Response Analysis:")
                print(f"   Has success indicators: {has_success}")
                print(f"   Has failure indicators: {has_failure}")
                
                # Special case: Check for the exact successful response we expect
                has_onvif_success = "SetNetworkInterfacesResponse" in response_text and "RebootNeeded" in response_text
                
                if has_failure and not has_onvif_success:
                    print("❌ Failure indicators detected in response")
                    return False
                
                if not has_success and not has_onvif_success:
                    print("❌ No clear success indicators found")
                    print("   This usually means the command was rejected")
                    return False
                
                if has_onvif_success:
                    print("✅ Valid ONVIF SetNetworkInterfacesResponse detected")
                else:
                    print("✅ Success indicators found in response")
                
                # Check if reboot is needed
                reboot_needed = True
                if "rebootneeded>false" in response_lower or "rebootneeded=\"false\"" in response_lower:
                    reboot_needed = False
                    print("   ℹ️  No reboot required")
                else:
                    print("   ⚠️  Camera may need reboot for changes to take effect")
                
                # Step 2: Wait and check if camera is still responsive at old IP
                print(f"\n🕐 Waiting for network change (5 seconds)...")
                time.sleep(5)
                
                # Step 2a: Check if camera's internal config actually changed
                print(f"🔍 Checking if camera's internal configuration changed...")
                new_config = self.get_current_network_config(old_ip, self.credentials["username"], self.credentials["password"])
                
                config_changed = False
                if new_config["addresses"]:
                    print(f"   Camera now reports IP addresses: {new_config['addresses']}")
                    if new_ip in new_config["addresses"]:
                        print(f"   ✅ Camera's internal config shows new IP {new_ip}")
                        config_changed = True
                    else:
                        print(f"   ❌ Camera's internal config still shows old IPs: {new_config['addresses']}")
                else:
                    print(f"   ⚠️  Could not read camera's current config")
                
                print(f"🔍 Testing if camera is still at old IP...")
                still_at_old = self.check_onvif_port(old_ip, 80, 3.0)
                print(f"   Camera still responding at {old_ip}: {'YES' if still_at_old else 'NO'}")
                
                # Step 3: Try to verify on new IP
                if config_changed or not still_at_old:
                    if self.verify_ip_change(new_ip, timeout=10):
                        # Update camera in list
                        for camera in self.cameras:
                            if camera.ip == old_ip:
                                camera.ip = new_ip
                                break
                        
                        print(f"✅ IP change verified and completed successfully!")
                        print(f"   {old_ip} → {new_ip}")
                        return True
                else:
                    print(f"❌ Verification failed - camera not accessible at {new_ip}")
                    
                    # If still at old IP, try alternative interface tokens
                    if still_at_old and len(all_tokens) > 1:
                        print(f"\n🔄 Trying alternative interface tokens...")
                        
                        print(f"\n🔄 Trying alternative approach: preserving LinkLocal and HwAddress...")
                        
                        # Get hardware address from current config
                        import re
                        hw_address = ""
                        if current_config["full_response"]:
                            hw_matches = re.findall(r'<ns2:HwAddress>([^<]+)</ns2:HwAddress>', current_config["full_response"])
                            if hw_matches:
                                hw_address = hw_matches[0]
                                print(f"   Found hardware address: {hw_address}")
                        
                        # Try with LinkLocal preserved as auto-generated and include HwAddress
                        alt_success = self.try_alternative_with_linklocal_preserved(
                            old_ip, new_ip, gateway, prefix_length, alt_token, hw_address
                        )
                        
                        if alt_success:
                            # Wait and verify again
                            time.sleep(5)
                            post_config = self.get_current_network_config(old_ip, self.credentials["username"], self.credentials["password"])
                            if post_config["addresses"] and new_ip in post_config["addresses"]:
                                print(f"✅ Alternative approach worked! Camera config updated.")
                                if self.verify_ip_change(new_ip, timeout=8):
                                    for camera in self.cameras:
                                        if camera.ip == old_ip:
                                            camera.ip = new_ip
                                            break
                                    print(f"✅ IP change successful with preserved LinkLocal!")
                                    print(f"   {old_ip} → {new_ip}")
                                    return True
                    
                    # If still at old IP, the command definitely didn't work
                    if still_at_old and not config_changed:
                        print(f"\n❌ FINAL DIAGNOSIS: Camera firmware does not support IP changes via ONVIF")
                        print(f"   - Camera accepts ONVIF command ✅")
                        print(f"   - Camera returns 'success' response ✅")
                        print(f"   - Camera internal config unchanged ❌")
                        print(f"   - Camera still responds at old IP ❌")
                        print(f"\n💡 ALTERNATIVE METHODS:")
                        print(f"   1. Use camera's web interface to change IP")
                        print(f"   2. Check camera manual for IP change procedure")
                        print(f"   3. Contact manufacturer about ONVIF support")
                        print(f"   4. Some cameras need firmware updates for ONVIF compatibility")
                        print(f"   5. Try manufacturer's specific software/tools")
                    elif still_at_old and config_changed:
                        print(f"\n❌ Camera updated config but network change failed")
                        print(f"   - Camera may need manual reboot despite saying 'no reboot needed'")
                        print(f"   - Try manually rebooting the camera now")
                    else:
                        print(f"\n❌ Partial success - investigate further")
                    
                    return False
            
            elif response.status_code == 401:
                print("❌ Authentication failed - check credentials")
                return False
            elif response.status_code == 404:
                print("❌ ONVIF service not found - camera may not support this operation")
                return False
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"❌ Connection timeout - camera not responding")
            return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Unable to connect to camera at {old_ip}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            self.logger.error(f"Error in IP change: {e}")
            return False
    
    def show_camera_details(self, camera: Camera) -> None:
        """Show detailed information about selected camera"""
        print(f"\n" + "="*50)
        print("CAMERA DETAILS")
        print("="*50)
        print(f"IP Address: {camera.ip}")
        print(f"Name: {camera.name}")
        print(f"Manufacturer: {camera.manufacturer or 'Unknown'}")
        print(f"Model: {camera.model or 'Unknown'}")
        print(f"Status: {'🟢 Reachable' if camera.reachable else '🔴 Unreachable'}")
        
        # Try to get additional info if credentials available
        if self.credentials["username"]:
            print("\nTesting connection...")
            test_camera = self.get_camera_info(camera.ip, self.credentials["username"], self.credentials["password"])
            if test_camera:
                print("✅ ONVIF connection successful")
            else:
                print("❌ ONVIF connection failed")
    
    def select_camera(self) -> Optional[Camera]:
        """Let user select a camera by ID"""
        if not self.cameras:
            print("❌ No cameras available")
            return None
        
        try:
            camera_id = input(f"Enter camera ID (1-{len(self.cameras)}) or 0 to cancel: ").strip()
            if camera_id == '0':
                return None
                
            idx = int(camera_id) - 1
            if 0 <= idx < len(self.cameras):
                return self.cameras[idx]
            else:
                print(f"❌ Invalid camera ID. Use 1-{len(self.cameras)}")
                return None
        except ValueError:
            print("❌ Please enter a valid number")
            return None
    
    def run(self) -> None:
        """Main program loop"""
        print("🎥 ONVIF Camera IP Changer - Interactive Menu")
        print("="*50)
        
        try:
            while True:
                self.display_cameras()
                choice = self.show_main_menu()
                
                if choice == '0':
                    print("\n👋 Goodbye!")
                    break
                elif choice == '1' or choice == '2':
                    if not self.current_network:
                        self.get_network_range()
                    if not self.credentials["username"]:
                        self.get_credentials()
                    print(f"\n🔄 Scanning {self.current_network}...")
                    self.cameras = self.scan_network_for_cameras(self.current_network)
                elif choice == '3':
                    if not self.cameras:
                        print("❌ No cameras available. Scan for cameras first.")
                        continue
                    if not self.credentials["username"]:
                        print("❌ Credentials required. Set credentials first.")
                        continue
                    camera = self.select_camera()
                    if camera:
                        self.change_camera_ip(camera)
                elif choice == '4':
                    if not self.cameras:
                        print("❌ No cameras available. Scan for cameras first.")
                        continue
                    camera = self.select_camera()
                    if camera:
                        self.show_camera_details(camera)
                elif choice == '5':
                    self.get_credentials()
                elif choice == '6':
                    self.get_network_range()
                    self.cameras = []  # Clear cameras when network changes
                else:
                    print("❌ Invalid choice. Please try again.")
                
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            self.logger.error(f"Unexpected error: {e}")

def main():
    """Main function"""
    try:
        changer = ONVIFIPChanger()
        changer.run()
    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
