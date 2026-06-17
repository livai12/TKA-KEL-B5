# Deployment Guide - Order Processing Service

## Architecture Overview

```
                           +-------------------+
                           |   VM1 (512MB)     |
                           |   Nginx LB +      |
   Users ─────────────────>|   Frontend        |
                           +--------+----------+
                                    |
                    ┌───────────────┼───────────────┐
                    │               │               │
             +------+------+ +-----+-------+ +-----+-------+
             | VM2 (2GB)   | | VM3 (2GB)   | | VM4 (2GB)   |
             | Flask +     | | Flask +     | | Flask +     |
             | Gunicorn    | | Gunicorn    | | Gunicorn    |
             +------+------+ +-----+-------+ +-----+-------+
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                           +--------+----------+
                           |   VM5 (4GB)       |
                           |   MongoDB 7.0     |
                           +-------------------+
```

| VM   | Role                       | Spec          | Monthly Cost |
|------|----------------------------|---------------|--------------|
| VM1  | Nginx Load Balancer + FE   | 1vCPU, 512MB  | $4           |
| VM2  | Flask App Server 1         | 1vCPU, 2GB    | $12          |
| VM3  | Flask App Server 2         | 1vCPU, 2GB    | $12          |
| VM4  | Flask App Server 3         | 1vCPU, 2GB    | $12          |
| VM5  | MongoDB Database           | 2vCPU, 4GB    | $24          |
| **Total** |                       |               | **$64**      |

---

## Prerequisites

- All VMs running **Ubuntu 22.04 LTS**
- SSH access to all VMs
- VMs can communicate with each other over the internal network
- Note your VM IPs:
  - `VM1_IP` = Nginx/Frontend
  - `VM2_IP` = App Server 1
  - `VM3_IP` = App Server 2
  - `VM4_IP` = App Server 3
  - `VM5_IP` = MongoDB Server

---

## Step 1: Upload Project Files to All VMs

From your local machine, upload the project to each VM:

```bash
# Upload to each VM (adjust paths as needed)
scp -r ./deploy ubuntu@VM5_IP:/home/ubuntu/
scp -r ./Resources/DB/dump ubuntu@VM5_IP:/home/ubuntu/

scp -r ./deploy ubuntu@VM2_IP:/home/ubuntu/
scp -r ./deploy ubuntu@VM3_IP:/home/ubuntu/
scp -r ./deploy ubuntu@VM4_IP:/home/ubuntu/

scp -r ./deploy ubuntu@VM1_IP:/home/ubuntu/
scp -r ./Resources/FE ubuntu@VM1_IP:/home/ubuntu/deploy/../Resources/FE
```

Alternatively, clone the Git repository on each VM:
```bash
git clone <your-repo-url> /home/ubuntu/project
```

---

## Step 2: Set Up MongoDB (VM5)

**SSH into VM5** and run:

```bash
ssh ubuntu@VM5_IP

# Make the script executable
chmod +x /home/ubuntu/deploy/setup_mongodb.sh

# Run the setup
sudo bash /home/ubuntu/deploy/setup_mongodb.sh
```

### Verify MongoDB

```bash
# Check service status
sudo systemctl status mongod

# Connect and verify data
mongosh orderdb --eval "db.orders.countDocuments({})"
# Expected: 10000

mongosh orderdb --eval "db.users.countDocuments({})"
# Expected: 505

mongosh orderdb --eval "db.products.countDocuments({})"
# Expected: 96

# Check indexes were created
mongosh orderdb --eval "db.orders.getIndexes()"

# Test connectivity from another terminal
mongosh "mongodb://VM5_IP:27017/orderdb" --eval "db.runCommand({ping:1})"
```

---

## Step 3: Set Up App Servers (VM2, VM3, VM4)

**Repeat on each app server VM.** Before running, edit the script to set `MONGO_URI` and `JWT_SECRET`.

```bash
ssh ubuntu@VM2_IP   # then VM3, VM4

# Edit placeholder variables
nano /home/ubuntu/deploy/setup_appserver.sh
# Change: MONGO_URI="mongodb://VM5_IP:27017/orderdb"
# Change: JWT_SECRET="your-secret-key-here" (must be same on all servers!)

# Make executable and run
chmod +x /home/ubuntu/deploy/setup_appserver.sh
sudo bash /home/ubuntu/deploy/setup_appserver.sh
```

> **IMPORTANT**: Use the **same JWT_SECRET** on all three app servers. If they differ, tokens issued by one server will be rejected by others.

### Verify Each App Server

```bash
# Check service is running
sudo systemctl status flask-app

# Test health endpoint
curl http://localhost:5000/health
# Expected: {"status":"ok","timestamp":"..."}

# Test product listing (should return data from MongoDB)
curl http://localhost:5000/products?limit=3 | python3 -m json.tool

# Check Gunicorn workers
ps aux | grep gunicorn
# Expected: 1 master + 3 worker processes

# Check logs if something is wrong
sudo journalctl -u flask-app -f
tail -f /var/log/gunicorn/error.log
```

---

## Step 4: Set Up Nginx Load Balancer (VM1)

**SSH into VM1** and edit the setup script to fill in app server IPs:

```bash
ssh ubuntu@VM1_IP

# Edit placeholder IPs
nano /home/ubuntu/deploy/setup_nginx.sh
# Set: APP_SERVER_1_IP="VM2_IP"
# Set: APP_SERVER_2_IP="VM3_IP"
# Set: APP_SERVER_3_IP="VM4_IP"

# Make executable and run
chmod +x /home/ubuntu/deploy/setup_nginx.sh
sudo bash /home/ubuntu/deploy/setup_nginx.sh
```

### Verify Nginx

```bash
# Check Nginx status
sudo systemctl status nginx

# Test frontend (should return HTML)
curl -s http://localhost/ | head -5

# Test API proxy (health check)
curl http://localhost/health
# Expected: {"status":"ok","timestamp":"..."}

# Test product listing through the load balancer
curl http://localhost/products?limit=2 | python3 -m json.tool

# Check Nginx config is valid
sudo nginx -t

# Watch access logs
sudo tail -f /var/log/nginx/access.log
```

---

## Step 5: End-to-End Verification

From any machine (preferably outside the cluster):

```bash
# 1. Frontend loads
curl -s http://VM1_IP/ | grep "Order Processing"

# 2. Health check
curl http://VM1_IP/health

# 3. List products
curl http://VM1_IP/products?limit=5

# 4. Login as admin
curl -X POST http://VM1_IP/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin1@tka.its.ac.id","password":"Admin@12345"}'
# Save the token from response

# 5. Login as user
curl -X POST http://VM1_IP/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user1@example.com","password":"User@12345"}'

# 6. Create an order (replace TOKEN with actual token)
curl -X POST http://VM1_IP/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"items":[{"product_id":"PRODUCT_ID","qty":1}],"payment_method":"transfer_bank"}'

# 7. Admin stats
curl http://VM1_IP/admin/stats \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Step 6: Run Locust Load Tests

From your **local machine** or a separate test machine (NOT from the server VMs):

```bash
# Install Locust
pip install locust

# Before each test scenario, save a snapshot on VM5:
ssh ubuntu@VM5_IP "bash /home/ubuntu/deploy/cleanup_orders.sh snapshot-save"

# Run Locust (replace VM1_IP with your Nginx LB IP)
locust -f Resources/Test/locustfile.py --host=http://VM1_IP

# Open Locust web UI at http://localhost:8089

# After each test, clean up on VM5:
ssh ubuntu@VM5_IP "bash /home/ubuntu/deploy/cleanup_orders.sh snapshot-clean"
ssh ubuntu@VM5_IP "bash /home/ubuntu/deploy/cleanup_orders.sh restore-stock"
```

### Locust Test Scenarios

| # | Scenario                   | Spawn Rate | Duration | Goal                                     |
|---|----------------------------|------------|----------|------------------------------------------|
| 1 | Maximum RPS (0% failure)   | Gradual    | 60s      | Find highest RPS with 0% failure          |
| 2 | Peak Concurrency           | 50/s       | 60s      | Max users before failure, spawn rate 50   |
| 3 | Peak Concurrency           | 100/s      | 60s      | Max users before failure, spawn rate 100  |
| 4 | Peak Concurrency           | 200/s      | 60s      | Max users before failure, spawn rate 200  |
| 5 | Peak Concurrency           | 500/s      | 60s      | Max users before failure, spawn rate 500  |

**Between each scenario:**
1. Stop Locust
2. Run `cleanup_orders.sh snapshot-clean` on VM5
3. Run `cleanup_orders.sh restore-stock` on VM5
4. Optionally restart app servers: `sudo systemctl restart flask-app`
5. Run `cleanup_orders.sh snapshot-save` on VM5
6. Start next Locust scenario

---

## Monitoring During Tests

Open separate SSH sessions to monitor each VM:

```bash
# On any VM - real-time resource usage
htop

# CPU and memory quick check
vmstat 1

# On VM1 - Nginx connections
watch -n 1 "curl -s http://localhost/nginx-status"

# On VM2/3/4 - Gunicorn logs
sudo tail -f /var/log/gunicorn/access.log

# On VM5 - MongoDB status
mongosh orderdb --eval "db.serverStatus().connections"
mongosh orderdb --eval "db.serverStatus().opcounters"
```

---

## Troubleshooting

### MongoDB Connection Refused

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Check bind IP
grep bindIp /etc/mongod.conf
# Must be 0.0.0.0 or include the app server IPs

# Check if port 27017 is listening
sudo ss -tlnp | grep 27017

# Check firewall
sudo ufw status
sudo ufw allow 27017    # Allow MongoDB port if firewall is active

# Check MongoDB logs
sudo tail -50 /var/log/mongodb/mongod.log
```

### Gunicorn Not Starting

```bash
# Check service status and logs
sudo systemctl status flask-app
sudo journalctl -u flask-app --no-pager -n 50

# Common issues:
# 1. Wrong MONGO_URI - can't connect to MongoDB
#    Fix: Check the IP in /etc/systemd/system/flask-app.service
# 2. Missing Python dependencies
#    Fix: /home/ubuntu/app/venv/bin/pip install -r requirements.txt
# 3. Permission errors
#    Fix: chown -R ubuntu:ubuntu /home/ubuntu/app /var/log/gunicorn
# 4. Port already in use
#    Fix: sudo lsof -i :5000

# Test Gunicorn manually (helpful for debugging)
cd /home/ubuntu/app
source venv/bin/activate
MONGO_URI="mongodb://VM5_IP:27017/orderdb" JWT_SECRET="your-secret" \
  gunicorn --workers 1 --bind 0.0.0.0:5000 app:app
```

### Nginx 502 Bad Gateway

This means Nginx cannot reach the Flask backends.

```bash
# Check if backends are running
curl http://VM2_IP:5000/health
curl http://VM3_IP:5000/health
curl http://VM4_IP:5000/health

# Check Nginx error log
sudo tail -30 /var/log/nginx/error.log
# Look for "Connection refused" or "no live upstreams"

# Verify upstream IPs in config
grep "server " /etc/nginx/sites-available/orderservice

# If IPs are wrong, fix them:
sudo nano /etc/nginx/sites-available/orderservice
sudo nginx -t
sudo systemctl reload nginx
```

### Nginx 504 Gateway Timeout

```bash
# Backend is too slow to respond
# 1. Check MongoDB performance
mongosh orderdb --eval "db.currentOp()"

# 2. Increase Nginx timeout (temporary fix)
# Edit proxy_read_timeout in /etc/nginx/sites-available/orderservice

# 3. Check if app servers are overloaded
ssh ubuntu@VM2_IP "htop"
```

### High Memory Usage on App Servers

```bash
# Check memory
free -h

# If Gunicorn workers are leaking memory, restart the service
sudo systemctl restart flask-app

# The max-requests=1000 setting should auto-recycle workers,
# but you can lower it if leaks are severe:
# Edit /etc/systemd/system/flask-app.service
# Change --max-requests to 500
# Then: sudo systemctl daemon-reload && sudo systemctl restart flask-app
```

### Frontend Not Loading / Shows Raw HTML

```bash
# Check if files exist
ls -la /var/www/frontend/

# Check file permissions
sudo chown -R www-data:www-data /var/www/frontend

# Check Nginx root directive
grep "root" /etc/nginx/sites-available/orderservice
```

---

## Quick Reference Commands

```bash
# -- Service Management --
sudo systemctl status flask-app       # App server status
sudo systemctl restart flask-app      # Restart app server
sudo systemctl status nginx           # Nginx status
sudo systemctl reload nginx           # Reload Nginx config (no downtime)
sudo systemctl status mongod          # MongoDB status

# -- Logs --
sudo journalctl -u flask-app -f       # App server logs (live)
sudo tail -f /var/log/nginx/error.log # Nginx error logs
sudo tail -f /var/log/mongodb/mongod.log  # MongoDB logs

# -- Config Editing --
sudo nano /etc/systemd/system/flask-app.service  # App server config
sudo nano /etc/nginx/sites-available/orderservice # Nginx site config
sudo nano /etc/mongod.conf                        # MongoDB config

# After editing systemd service:
sudo systemctl daemon-reload && sudo systemctl restart flask-app

# After editing Nginx config:
sudo nginx -t && sudo systemctl reload nginx

# After editing mongod.conf:
sudo systemctl restart mongod
```
