def quick_add(request):
    """Adds to every template: the quick-add expense form (modal in base.html), whether this is a demo
    sandbox account (banner), and whether the 'Try the demo' button should be offered."""
    from core.demo import demo_enabled
    context = {"demo_enabled": demo_enabled()}
    if request.user.is_authenticated:
        from expenses.forms import ExpenseForm
        profile = getattr(request.user, "profile", None)
        context.update({"quick_expense_form": ExpenseForm(user=request.user, auto_id="qe_%s"),
                        "is_demo": bool(profile and profile.is_demo)})
    return context
