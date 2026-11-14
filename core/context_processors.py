def quick_add(request):
    """Makes the quick-add expense form available on every page (modal in base.html)."""
    if request.user.is_authenticated:
        from expenses.forms import ExpenseForm
        return {"quick_expense_form": ExpenseForm(user=request.user, auto_id="qe_%s")}
    return {}
