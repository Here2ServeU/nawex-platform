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

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
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
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/userdata.sh", {
    admin_password = var.admin_password
    hec_token      = var.hec_token
  })

  tags = {
    Name = var.name
    Role = "splunk-enterprise"
  }
}
