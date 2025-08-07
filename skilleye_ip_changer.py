#!/usr/bin/env python3
"""
Interactive batch IP changer for ONVIF cameras
Enhanced version with user interface and input validation
"""

import requests
import logging
import json
import os
import getpass
from datetime import datetime
from typing import Dict, Tuple, Optional
import ipaddress
import sys

class ONVIFIPChanger:
    def __init__(self):
        self.setup_logging()
        self.config = self.load_config()
        
    def setup_logging(self):
        """Configure logging system"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"ip_change_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        logging.info(f"Script started - Log saved to: {log_filename}")
    
    def load_config(self) -> dict:
        """Load configuration from JSON file if exists"""
        config_file = "camera_config.json"
        default_config = {
            "username": "admin",
            "password": "",
            "prefix_length": 24,
            "gateway": "192.168.1.1",
            "interface_token": "eth0",
            "timeout": 10,
            "cameras": {}
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logging.info("Configuration loaded from file")
                    return {**default_config, **config}
            except Exception as e:
                logging.warning(f"Error loading config: {e}")
        
        return default_config
    
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            # Don't save password to file for security
            config_to_save = self.config.copy()
            config_to_save['password'] = ""
            
            with open("camera_config.json", 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
            logging.info("Configuration saved")
        except Exception as e:
            logging.error(f"Error saving config: {e}")
    
    def validate_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ipaddress.AddressValueError:
            return False
    
    def get_credentials(self) -> Tuple[str, str]:
        """Get user credentials"""
        print("\n=== CAMERA CREDENTIALS ===")
        
        # Username
        default_user = self.config.get('username', 'admin')
        username = input(f"Username [{default_user}]: ").strip()
        if not username:
            username = default_user
        
        # Password
        if self.config.get('password'):
            use_saved = input("Use saved password? (y/n) [y]: ").strip().lower()
            if use_saved in ['', 'y', 'yes']:
                password = self.config['password']
            else:
                password = getpass.getpass("Password: ")
        else:
            password = getpass.getpass("Password: ")
        
        return username, password
    
    def get_network_config(self) -> Tuple[str, int]:
        """Get network configuration"""
        print("\n=== NETWORK CONFIGURATION ===")
        
        # Gateway
        default_gateway = self.config.get('gateway', '192.168.1.1')
        gateway = input(f"Gateway [{default_gateway}]: ").strip()
        if not gateway:
            gateway = default_gateway
        elif not self.validate_ip(gateway):
            print("⚠️  Invalid Gateway IP, using default")
            gateway = default_gateway
        
        # Prefix length
        default_prefix = self.config.get('prefix_length', 24)
        try:
            prefix_input = input(f"Prefix Length [{default_prefix}]: ").strip()
            prefix_length = int(prefix_input) if prefix_input else default_prefix
            if not (8 <= prefix_length <= 30):
                print("⚠️  Invalid prefix length (8-30), using default")
                prefix_length = default_prefix
        except ValueError:
            prefix_length = default_prefix
        
        return gateway, prefix_length
    
    def get_camera_list(self) -> Dict[str, str]:
        """Manage camera list interactively"""
        cameras = {}
        
        print("\n=== CAMERA LIST ===")
        print("Enter cameras to reconfigure")
        print("Format: CURRENT_IP -> NEW_IP")
        print("(Press ENTER on empty IP to finish)")
        
        # Show saved cameras if they exist
        saved_cameras = self.config.get('cameras', {})
        if saved_cameras:
            print(f"\nSaved cameras ({len(saved_cameras)}):")
            for old_ip, new_ip in saved_cameras.items():
                print(f"  {old_ip} -> {new_ip}")
            
            use_saved = input("\nUse saved list? (y/n/e for edit) [y]: ").strip().lower()
            if use_saved in ['', 'y', 'yes']:
                return saved_cameras
            elif use_saved in ['e', 'edit']:
                cameras = saved_cameras.copy()
                print("Edit mode - current list loaded")
        
        counter = len(cameras) + 1
        
        while True:
            print(f"\n--- Camera #{counter} ---")
            
            # Current IP
            old_ip = input("Current IP: ").strip()
            if not old_ip:
                break
            
            if not self.validate_ip(old_ip):
                print("❌ Invalid current IP")
                continue
            
            # New IP
            new_ip = input("New IP: ").strip()
            if not new_ip:
                print("❌ New IP required")
                continue
            
            if not self.validate_ip(new_ip):
                print("❌ Invalid new IP")
                continue
            
            if old_ip == new_ip:
                print("⚠️  Identical IPs, operation unnecessary")
                continue
            
            cameras[old_ip] = new_ip
            print(f"✅ Added: {old_ip} -> {new_ip}")
            counter += 1
        
        return cameras
    
    def confirm_operation(self, cameras: Dict[str, str], username: str, gateway: str, prefix_length: int) -> bool:
        """Show summary and request confirmation"""
        print("\n" + "="*50)
        print("OPERATION SUMMARY")
        print("="*50)
        print(f"Username: {username}")
        print(f"Gateway: {gateway}")
        print(f"Subnet: /{prefix_length}")
        print(f"Cameras to modify: {len(cameras)}")
        print()
        
        for old_ip, new_ip in cameras.items():
            print(f"  {old_ip} -> {new_ip}")
        
        print("\n⚠️  WARNING: This operation will modify the network configuration of the cameras!")
        print("   Make sure the new IPs are correct and reachable.")
        
        confirm = input("\nProceed? (y/n) [n]: ").strip().lower()
        return confirm in ['y', 'yes']
    
    def change_camera_ip(self, old_ip: str, new_ip: str, username: str, password: str, 
                        gateway: str, prefix_length: int, interface_token: str, timeout: int) -> bool:
        """Change IP of a single camera"""
        url = f"http://{old_ip}/onvif/device_service"
        logging.info(f"Changing IP: {old_ip} -> {new_ip}")
        
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
                  <tt:Manual>
                    <tt:Address>{new_ip}</tt:Address>
                    <tt:PrefixLength>{prefix_length}</tt:PrefixLength>
                  </tt:Manual>
                  <tt:DHCP>false</tt:DHCP>
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
                data=soap_body, 
                headers=headers,
                auth=(username, password),
                timeout=timeout
            )
            
            logging.info(f"  HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                if b"<RebootNeeded>false" in response.content:
                    logging.info("  ✅ Change completed (no reboot required)")
                    print(f"✅ {old_ip} -> {new_ip} (completed)")
                else:
                    logging.info("  ✅ Change completed (may require reboot)")
                    print(f"✅ {old_ip} -> {new_ip} (may require reboot)")
                return True
            elif response.status_code == 401:
                logging.error("  ❌ Authentication error")
                print(f"❌ {old_ip}: Authentication error")
                return False
            else:
                logging.warning(f"  ⚠️  Unexpected response: {response.status_code}")
                print(f"⚠️  {old_ip}: HTTP response {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logging.error(f"  ❌ Connection timeout with {old_ip}")
            print(f"❌ {old_ip}: Connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            logging.error(f"  ❌ Unable to connect to {old_ip}")
            print(f"❌ {old_ip}: Unable to connect")
            return False
        except Exception as e:
            logging.error(f"  ❌ Generic error with {old_ip}: {e}")
            print(f"❌ {old_ip}: Error - {str(e)}")
            return False
    
    def run(self):
        """Execute main process"""
        print("🎥 ONVIF IP Changer - Interactive Script")
        print("="*50)
        
        try:
            # Get credentials
            username, password = self.get_credentials()
            
            # Get network configuration  
            gateway, prefix_length = self.get_network_config()
            
            # Get camera list
            cameras = self.get_camera_list()
            
            if not cameras:
                print("\n❌ No cameras to configure")
                return
            
            # Confirm operation
            if not self.confirm_operation(cameras, username, gateway, prefix_length):
                print("\n❌ Operation cancelled by user")
                return
            
            # Update configuration
            self.config.update({
                'username': username,
                'password': password,  # Will be removed in save
                'gateway': gateway,
                'prefix_length': prefix_length,
                'cameras': cameras
            })
            
            # Save configuration (without password)
            self.save_config()
            
            # Execute changes
            print(f"\n🚀 Starting changes on {len(cameras)} cameras...")
            print("-" * 50)
            
            success_count = 0
            interface_token = self.config.get('interface_token', 'eth0')
            timeout = self.config.get('timeout', 10)
            
            for old_ip, new_ip in cameras.items():
                success = self.change_camera_ip(
                    old_ip, new_ip, username, password,
                    gateway, prefix_length, interface_token, timeout
                )
                if success:
                    success_count += 1
                
                print()  # Empty line for separation
            
            # Final summary
            print("="*50)
            print("FINAL SUMMARY")
            print("="*50)
            print(f"Cameras processed: {len(cameras)}")
            print(f"Successes: {success_count}")
            print(f"Failures: {len(cameras) - success_count}")
            
            if success_count == len(cameras):
                print("🎉 All changes completed successfully!")
            elif success_count > 0:
                print("⚠️  Some changes completed, check logs for details")
            else:
                print("❌ No changes completed")
            
            logging.info(f"Process completed: {success_count}/{len(cameras)} successes")
            
        except KeyboardInterrupt:
            print("\n\n❌ Operation interrupted by user")
            logging.info("Operation interrupted by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            logging.error(f"Unexpected error: {e}")

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
