resource "aws_vpc" "prod_network" {
  cidr_block = "10.10.0.0/16"
  tags = {
    Name = "prod-network"
  }
}

resource "aws_vpc_peering_connection" "shared_services" {
  peer_owner_id = "210000000004"
  vpc_id        = aws_vpc.prod_network.id
  peer_vpc_id   = "vpc-shared-services"
}

resource "aws_flow_log" "prod" {
  vpc_id = aws_vpc.prod_network.id
}
