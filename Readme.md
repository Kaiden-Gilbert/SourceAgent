# 🏛️ Source Agent

![Status](https://img.shields.io/badge/Status-Active-success)
![Environment](https://img.shields.io/badge/Environment-Local%20%7C%20Offline-blue)
![Updates](https://img.shields.io/badge/Updates-Cloud%20Synced-orange)

> **The localized, autonomous counterpart to the online Policy Advisor.**

Welcome to **Source Agent**. This application is a fully localized intelligence node designed to operate directly on your machine. By bridging the power of the online Policy Advisor with local architecture, Source Agent allows you to securely inject your own custom knowledge bases, documentation, and data to assist with workflow, compliance, and general inquiries.

---

## Core Capabilities
* **Custom Knowledge Integration:** Feed the AI your specific documents to tailor its expertise exactly to your workflow.
* **Air-Gapped Operation:** Once initialized, the core engine is capable of running entirely offline, ensuring your data never has to leave your device.
* **Seamless Cloud Syncing:** When connected to the internet, the app silently checks for the latest feature updates and prompts you when an upgrade is ready.

---

## Connectivity & Boot Protocol

Source Agent is designed for offline sovereignty, but it utilizes a smart-boot system to ensure you always have the most stable build.

### 1. The Initial Initialization (Internet Required)
When you boot Source Agent for the very first time, **an active internet connection is mandatory.** The agent must reach out to the repository to pull the latest core engine and dependencies. If the system cannot detect a connection during this first run, it will display a network error and close safely.

### 2. Standard Operation (Offline Capable)
Once the initial setup is complete, you are free to disconnect. The agent boots seamlessly entirely offline. 

### 3. The Update Ping
If you boot the agent while connected to the internet, it will quickly ping the server. If a new update is detected, you will receive a notification prompting a restart to apply the latest features. If you are offline, this ping is simply bypassed, and your current local version will launch without interruption.

---

## Support & Feedback

This project is actively maintained. If you encounter any bugs, experience unexpected behavior, or have feature recommendations to improve the agent, please reach out.

**Maintainer:** Kaiden Gilbert  
**Owner:** Kaiden Gilbert

*Please submit all bug reports or feature requests via email or by opening an Issue in this repository.*
