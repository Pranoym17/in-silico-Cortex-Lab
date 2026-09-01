locals {
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
  name_prefix        = "cortex-lab-${var.environment}"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.${var.environment == "production" ? 20 : 10}.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }

resource "aws_subnet" "public" {
  for_each                = toset(local.availability_zones)
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, index(local.availability_zones, each.value))
  map_public_ip_on_launch = true
}

resource "aws_subnet" "app" {
  for_each          = toset(local.availability_zones)
  vpc_id            = aws_vpc.main.id
  availability_zone = each.value
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, 20 + index(local.availability_zones, each.value))
}

resource "aws_subnet" "data" {
  for_each          = toset(local.availability_zones)
  vpc_id            = aws_vpc.main.id
  availability_zone = each.value
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, 40 + index(local.availability_zones, each.value))
}

resource "aws_route_table" "public" { vpc_id = aws_vpc.main.id }
resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# Portfolio cost profile: ECS tasks use public subnets only for outbound access
# to Supabase, Modal, and S3. Their security groups still prevent direct inbound
# access; RDS and Redis remain in subnets with no internet route. This removes
# the always-on NAT Gateway and its public IPv4 charge.
