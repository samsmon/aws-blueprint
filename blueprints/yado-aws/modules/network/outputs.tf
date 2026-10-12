output "vpc_id" {
  value = aws_vpc.this.id
}

output "vpc_cidr" {
  value = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  value = [for s in aws_subnet.public : s.id]
}

output "private_subnet_ids" {
  value = [for s in aws_subnet.private : s.id]
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "db_clients_security_group_id" {
  value = aws_security_group.db_clients.id
}
