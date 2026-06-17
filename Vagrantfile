# -*- mode: ruby -*-
# vi: set ft=ruby :
# ===========================================================================
# Vagrantfile - FP TKA 26 VM Provisioning
# ===========================================================================
# Membuat 5 VM sesuai arsitektur:
#   VM1: Nginx Load Balancer + Frontend (512MB)
#   VM2: App Server 1 (2GB)
#   VM3: App Server 2 (2GB)
#   VM4: App Server 3 (2GB)
#   VM5: MongoDB Database Server (4GB)
#
# Catatan:
#   - Vagrantfile ini untuk SATU komputer. Jika menggunakan 2 komputer,
#     bagi VM sesuai kebutuhan dan sesuaikan IP di masing-masing Vagrantfile.
#   - Menggunakan private network dengan IP statis.
#   - Ubah IP sesuai jaringan Anda.
#
# Penggunaan:
#   vagrant up              # Buat semua VM
#   vagrant up vm5          # Buat VM tertentu saja
#   vagrant ssh vm1         # SSH ke VM
#   vagrant halt            # Matikan semua VM
#   vagrant destroy -f      # Hapus semua VM
# ===========================================================================

# IP Address Configuration
# Sesuaikan subnet ini dengan jaringan Anda
IP_VM1_LB       = "192.168.56.10"  # Nginx Load Balancer
IP_VM2_APP1     = "192.168.56.11"  # App Server 1
IP_VM3_APP2     = "192.168.56.12"  # App Server 2
IP_VM4_APP3     = "192.168.56.13"  # App Server 3
IP_VM5_MONGODB  = "192.168.56.14"  # MongoDB

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"   # Ubuntu 22.04 LTS
  config.vm.box_check_update = false

  # =========================================================================
  # VM5: MongoDB Database Server (Deploy ini PERTAMA)
  # Tipe: vm5 (2vCPU, 4GB RAM) - $24/bulan
  # =========================================================================
  config.vm.define "vm5" do |db|
    db.vm.hostname = "db-server"
    db.vm.network "private_network", ip: IP_VM5_MONGODB

    db.vm.provider "virtualbox" do |vb|
      vb.name   = "FP-TKA26-MongoDB"
      vb.memory = 4096
      vb.cpus   = 2
    end

    # Sync project files ke VM
    db.vm.synced_folder ".", "/vagrant", type: "virtualbox"

    db.vm.provision "shell", inline: <<-SHELL
      echo "[INFO] VM5 (MongoDB) is ready."
      echo "[INFO] To setup MongoDB, SSH in and run:"
      echo "       cd /vagrant/deploy && bash setup_mongodb.sh"
    SHELL
  end

  # =========================================================================
  # VM2: App Server 1
  # Tipe: vm3 (1vCPU, 2GB RAM) - $12/bulan
  # =========================================================================
  config.vm.define "vm2" do |app1|
    app1.vm.hostname = "app-server-1"
    app1.vm.network "private_network", ip: IP_VM2_APP1

    app1.vm.provider "virtualbox" do |vb|
      vb.name   = "FP-TKA26-App1"
      vb.memory = 2048
      vb.cpus   = 1
    end

    app1.vm.synced_folder ".", "/vagrant", type: "virtualbox"

    app1.vm.provision "shell", inline: <<-SHELL
      echo "[INFO] VM2 (App Server 1) is ready."
      echo "[INFO] To deploy backend, SSH in and run:"
      echo "       cd /vagrant/deploy && bash setup_appserver.sh"
      echo "[INFO] IMPORTANT: Edit MONGO_URI in setup_appserver.sh first!"
      echo "       Set MONGO_URI to: mongodb://#{IP_VM5_MONGODB}:27017/"
    SHELL
  end

  # =========================================================================
  # VM3: App Server 2
  # Tipe: vm3 (1vCPU, 2GB RAM) - $12/bulan
  # =========================================================================
  config.vm.define "vm3" do |app2|
    app2.vm.hostname = "app-server-2"
    app2.vm.network "private_network", ip: IP_VM3_APP2

    app2.vm.provider "virtualbox" do |vb|
      vb.name   = "FP-TKA26-App2"
      vb.memory = 2048
      vb.cpus   = 1
    end

    app2.vm.synced_folder ".", "/vagrant", type: "virtualbox"

    app2.vm.provision "shell", inline: <<-SHELL
      echo "[INFO] VM3 (App Server 2) is ready."
      echo "[INFO] To deploy backend, SSH in and run:"
      echo "       cd /vagrant/deploy && bash setup_appserver.sh"
      echo "[INFO] IMPORTANT: Edit MONGO_URI in setup_appserver.sh first!"
      echo "       Set MONGO_URI to: mongodb://#{IP_VM5_MONGODB}:27017/"
    SHELL
  end

  # =========================================================================
  # VM4: App Server 3
  # Tipe: vm3 (1vCPU, 2GB RAM) - $12/bulan
  # =========================================================================
  config.vm.define "vm4" do |app3|
    app3.vm.hostname = "app-server-3"
    app3.vm.network "private_network", ip: IP_VM4_APP3

    app3.vm.provider "virtualbox" do |vb|
      vb.name   = "FP-TKA26-App3"
      vb.memory = 2048
      vb.cpus   = 1
    end

    app3.vm.synced_folder ".", "/vagrant", type: "virtualbox"

    app3.vm.provision "shell", inline: <<-SHELL
      echo "[INFO] VM4 (App Server 3) is ready."
      echo "[INFO] To deploy backend, SSH in and run:"
      echo "       cd /vagrant/deploy && bash setup_appserver.sh"
      echo "[INFO] IMPORTANT: Edit MONGO_URI in setup_appserver.sh first!"
      echo "       Set MONGO_URI to: mongodb://#{IP_VM5_MONGODB}:27017/"
    SHELL
  end

  # =========================================================================
  # VM1: Nginx Load Balancer + Frontend (Deploy ini TERAKHIR)
  # Tipe: vm1 (1vCPU, 512MB RAM) - $4/bulan
  # =========================================================================
  config.vm.define "vm1" do |lb|
    lb.vm.hostname = "load-balancer"
    lb.vm.network "private_network", ip: IP_VM1_LB

    lb.vm.provider "virtualbox" do |vb|
      vb.name   = "FP-TKA26-Nginx"
      vb.memory = 512
      vb.cpus   = 1
    end

    lb.vm.synced_folder ".", "/vagrant", type: "virtualbox"

    lb.vm.provision "shell", inline: <<-SHELL
      echo "[INFO] VM1 (Nginx Load Balancer) is ready."
      echo "[INFO] To setup Nginx, SSH in and run:"
      echo "       cd /vagrant/deploy && bash setup_nginx.sh"
      echo "[INFO] IMPORTANT: Edit IP addresses in setup_nginx.sh first!"
      echo "       APP_SERVER_1_IP=#{IP_VM2_APP1}"
      echo "       APP_SERVER_2_IP=#{IP_VM3_APP2}"
      echo "       APP_SERVER_3_IP=#{IP_VM4_APP3}"
    SHELL
  end

end
