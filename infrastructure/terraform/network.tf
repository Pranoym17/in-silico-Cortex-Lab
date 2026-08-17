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

resource "aws_eip" "nat" { domain = "vpc" }
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = values(aws_subnet.public)[0].id
  depends_on    = [aws_internet_gateway.main]
}
resource "aws_route_table" "private" { vpc_id = aws_vpc.main.id }
resource "aws_route" "private_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main.id
}
resource "aws_route_table_association" "app" {
  for_each       = aws_subnet.app
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}
resource "aws_route_table_association" "data" {
  for_each       = aws_subnet.data
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}
