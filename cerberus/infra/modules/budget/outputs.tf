# Budget Module Outputs

output "budget_id" {
  description = "The ID of the budget"
  value       = aws_budgets_budget.monthly.id
}

output "budget_name" {
  description = "The name of the budget"
  value       = aws_budgets_budget.monthly.name
}
