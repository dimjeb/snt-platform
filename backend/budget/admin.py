from django.contrib import admin

from .models import Budget, BudgetItem, Expense


class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 0


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("organization", "year", "status", "approved_at")
    list_filter = ("status",)
    inlines = [BudgetItemInline]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("organization", "date", "amount", "item", "counterparty")
