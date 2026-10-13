terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }
  }
}

resource "aws_security_group" "splunk_sg" {
  name        = "${var.name}-sg"
  description = "Security group for Splunk Enterprise"
  vpc_id      = var.vpc_id

  ingress {
    description = "Splunk Web UI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  ingress {
    description = "Splunk HEC"
    from_port   = 8088
    to_port     = 8088
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  # Egress only for package / Splunk downloads (HTTP/HTTPS) to an explicit
  # allow-list (NAT, proxy or VPC endpoint ranges). Empty = no egress.
  dynamic "egress" {
    for_each = length(var.egress_cidr_blocks) > 0 ? toset([80, 443]) : toset([])
    content {
      description = "Outbound TCP ${egress.value}"
      from_port   = egress.value
      to_port     = egress.value
      protocol    = "tcp"
      cidr_blocks = var.egress_cidr_blocks
    }
  }

  tags = {
    Name = "${var.name}-sg"
  }
}

resource "aws_instance" "splunk" {
  ami                         = var.ami
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.splunk_sg.id]
  key_name                    = var.key_name
  associate_public_ip_address = var.associate_public_ip

  # IMDSv2 only
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = var.root_volume_size
  }

  user_data = templatefile("${path.module}/userdata.sh", {
    admin_password = var.admin_password
    hec_token      = var.hec_token
  })

  tags = {
    Name = var.name
    Role = "splunk-enterprise"
  }
}
