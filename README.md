# skilleye_cameras_change_ip
This is a python script that allows to change IP on SkillEye cameras I tried it with the model: SEI‑E4121UI
# ONVIF IP Changer 🎥

An interactive Python script for batch changing IP addresses of ONVIF-compatible security cameras. This tool provides a user-friendly interface for reconfiguring multiple cameras' network settings through the ONVIF protocol.

## ✨ Features

- **Interactive Interface**: Step-by-step guided process with user-friendly prompts
- **Input Validation**: Real-time validation of IP addresses and network settings
- **Configuration Management**: Save and reuse settings with JSON configuration files
- **Secure Credentials**: Hidden password input and optional credential storage
- **Robust Error Handling**: Detailed error reporting for connection, authentication, and network issues
- **Comprehensive Logging**: Timestamped logs with both file and console output
- **Batch Operations**: Process multiple cameras in a single run
- **Operation Preview**: Review all changes before execution

## 🚀 Quick Start

### Prerequisites

```bash
pip install requests
```

### Basic Usage

1. **Run the script**:
   ```bash
   python onvif_ip_changer.py
   ```

2. **Follow the interactive prompts**:
   - Enter camera credentials (username/password)
   - Configure network settings (gateway, subnet mask)
   - Add cameras to modify (current IP → new IP)
   - Review and confirm the operation

3. **Monitor progress**:
   - Real-time status updates during execution
   - Detailed logs saved to timestamped files
   - Final summary with success/failure counts

## 📋 Requirements

- Python 3.6+
- `requests` library
- ONVIF-compatible IP cameras
- Network access to cameras on their current IP addresses

## 🛠️ Configuration

The script automatically creates a `camera_config.json` file to store your settings:

```json
{
  "username": "admin",
  "gateway": "192.168.1.1",
  "prefix_length": 24,
  "interface_token": "eth0",
  "timeout": 10,
  "cameras": {
    "192.168.1.100": "192.168.1.150",
    "192.168.1.101": "192.168.1.151"
  }
}
```

### Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `username` | Camera login username | `admin` |
| `gateway` | Network gateway IP | `192.168.1.1` |
| `prefix_length` | Subnet mask (CIDR notation) | `24` |
| `interface_token` | Network interface identifier | `eth0` |
| `timeout` | Connection timeout in seconds | `10` |
| `cameras` | Dictionary of old_ip → new_ip mappings | `{}` |

## 📝 Usage Examples

### Example 1: Single Camera
```
Current IP: 192.168.1.100
New IP: 192.168.1.200
```

### Example 2: Multiple Cameras
```
Camera #1: 10.0.1.50 → 192.168.1.50
Camera #2: 10.0.1.51 → 192.168.1.51
Camera #3: 10.0.1.52 → 192.168.1.52
```

### Example 3: Using Saved Configuration
The script can reuse previously saved camera lists and network settings, making repeated operations quick and easy.

## 🔧 ONVIF Protocol Details

This script uses the ONVIF `SetNetworkInterfaces` command to modify camera network settings. The SOAP request includes:

- **IPv4 Configuration**: Static IP assignment with manual addressing
- **Gateway Setting**: Network gateway configuration
- **Interface Management**: Network interface enable/disable controls
- **DHCP Control**: Disables DHCP for static IP assignment

## 📊 Output & Logging

### Console Output
- Real-time progress updates
- Success/failure status for each camera
- Final operation summary
- Error messages with suggestions

### Log Files
- Timestamped log files: `ip_change_YYYYMMDD_HHMMSS.log`
- Detailed HTTP responses and error traces
- Configuration changes tracking
- Complete operation audit trail

## ⚠️ Important Considerations

### Network Planning
- **IP Conflicts**: Ensure new IP addresses don't conflict with existing devices
- **Subnet Compatibility**: Verify new IPs are in the correct subnet range
- **Gateway Accessibility**: Confirm the gateway IP is reachable from new addresses

### Camera Compatibility
- **ONVIF Support**: Cameras must support ONVIF protocol
- **Authentication**: Default credentials are often `admin/admin` or `admin/123456`
- **Firmware**: Some older firmware versions may have limited ONVIF support

### Security Notes
- **Credential Storage**: Passwords are not saved to configuration files
- **Network Security**: Use this tool only on trusted networks
- **Authentication**: Always change default camera passwords

## 🔍 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `Authentication error` | Wrong username/password | Verify camera credentials |
| `Connection timeout` | Network unreachable | Check IP address and network connectivity |
| `HTTP 404/500` | ONVIF not supported | Verify camera ONVIF compatibility |
| `Invalid IP` | Malformed IP address | Use valid IPv4 format (e.g., 192.168.1.100) |

### Debug Tips

1. **Check connectivity**: `ping <camera_ip>`
2. **Verify ONVIF**: Access `http://<camera_ip>/onvif/device_service` in browser
3. **Review logs**: Check detailed error messages in log files
4. **Test credentials**: Try logging into camera web interface

## 📁 File Structure

```
project/
├── onvif_ip_changer.py     # Main script
├── camera_config.json      # Configuration file (auto-created)
├── ip_change_*.log         # Log files (auto-created)
└── README.md              # This file
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly with different camera models
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter issues:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Review the log files for detailed error information
3. Open an issue with:
   - Camera model and firmware version
   - Error messages from logs
   - Network configuration details
   - Steps to reproduce the issue

## 🙏 Acknowledgments

- [ONVIF](https://www.onvif.org/) for the standardized IP camera protocol
- [Python Requests](https://docs.python-requests.org/) for HTTP handling
- Security camera manufacturers supporting ONVIF standards

---

**⚡ Made with ❤️ for network administrators and security professionals**
