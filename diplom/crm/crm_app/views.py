from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Client, Order, Inventory, Product, OrderItem
from django.db.models import Sum, F
from django.db import transaction  # Додано для безпечних транзакцій
from django.http import HttpResponse
import openpyxl
from datetime import datetime

@login_required
def dashboard(request):
    # Визначаємо права на основі груп користувача
    user_groups = request.user.groups.values_list('name', flat=True)
    is_admin = request.user.is_superuser or "admin" in user_groups
    is_manager = "Manager1" in user_groups or is_admin
    is_stafflog = "Stafflog" in user_groups or is_admin

    # 1. ДОДАВАННЯ КЛІЄНТА (Тільки Admin та Manager)
    if request.method == 'POST' and 'add_client' in request.POST:
        if is_manager:
            Client.objects.create(
                name=request.POST.get('name'),
                phone=request.POST.get('phone'),
                email=request.POST.get('email'),
                client_type=request.POST.get('client_type')
            )
        return redirect('dashboard')

    # 2. СТВОРЕННЯ ЗАМОВЛЕННЯ (Тільки Admin та Manager)
    if request.method == 'POST' and 'add_order' in request.POST:
        if is_manager:
            client_id = request.POST.get('client_id')
            product_ids = request.POST.getlist('product_id[]')
            quantities = request.POST.getlist('quantity[]')

            if client_id and product_ids:
                try:
                    with transaction.atomic():
                        new_order = Order.objects.create(
                            client_id=client_id,
                            manager=request.user,
                            status=request.POST.get('status'),
                            total_amount=0  
                        )
                        
                        calculated_total = 0

                        for p_id, qty in zip(product_ids, quantities):
                            if not p_id: 
                                continue
                            
                            try:
                                qty = int(qty)
                            except ValueError:
                                continue

                            if qty <= 0:
                                continue
                                
                            product_obj = Product.objects.get(id=p_id)
                            inv = Inventory.objects.get(product=product_obj)
                            
                            if inv.quantity < qty:
                                raise ValueError(f"Недостатньо товару {product_obj.name} на складі.")

                            item_price = product_obj.price
                            calculated_total += item_price * qty

                            OrderItem.objects.create(
                                order=new_order,
                                product=product_obj,
                                quantity=qty,
                                price=item_price
                            )
                            
                            inv.quantity -= qty
                            inv.save()

                        new_order.total_amount = calculated_total
                        new_order.save()
                        
                except (Product.DoesNotExist, Inventory.DoesNotExist, ValueError):
                    pass
                    
        return redirect('dashboard')

    # 3. ЗМІНА СТАТУСУ ЗАМОВЛЕННЯ (Тільки Admin та Manager)
    if request.method == 'POST' and 'update_status' in request.POST:
        if is_manager:
            try:
                order = Order.objects.get(id=request.POST.get('order_id'))
                old_status = order.status
                new_status = request.POST.get('new_status')
                items = OrderItem.objects.filter(order=order)

                if new_status == "Скасовано" and old_status != "Скасовано":
                    for item in items:
                        inv = Inventory.objects.get(product=item.product)
                        inv.quantity += item.quantity
                        inv.save()
                elif old_status == "Скасовано" and new_status != "Скасовано":
                    for item in items:
                        inv = Inventory.objects.get(product=item.product)
                        inv.quantity -= item.quantity
                        inv.save()

                order.status = new_status
                order.save()
            except Order.DoesNotExist:
                pass
        return redirect('dashboard')

    # 4. ПРИХІД ТОВАРУ НА СКЛАД (Тільки Admin та Stafflog) - ВИПРАВЛЕНО БЕЗПЕКУ ДАНИХ
    if request.method == 'POST' and 'add_inventory' in request.POST:
        if is_stafflog:
            # Безпечно конвертуємо числові значення, щоб уникнути падіння та редиректів
            try:
                raw_price = request.POST.get('price')
                price = float(raw_price) if raw_price and raw_price.strip() else 0.0
                
                raw_quantity = request.POST.get('quantity')
                quantity = int(raw_quantity) if raw_quantity and raw_quantity.strip() else 0
                
                raw_min_qty = request.POST.get('min_qty')
                min_qty = int(raw_min_qty) if raw_min_qty and raw_min_qty.strip() else 0
            except ValueError:
                # Якщо користувач ввів текст замість цифр, ставимо безпечні значення за замовчуванням
                price = 0.0
                quantity = 0
                min_qty = 0

            # Безпечна робота з датою
            arrival_date = request.POST.get('arrival_date')
            if not arrival_date or not arrival_date.strip():
                arrival_date = datetime.now().date()

            try:
                with transaction.atomic():
                    new_prod = Product.objects.create(
                        name=request.POST.get('prod_name'),
                        category=request.POST.get('category'),
                        price=price,
                        supplier=request.POST.get('supplier') 
                    )
                    
                    Inventory.objects.create(
                        product=new_prod,
                        quantity=quantity,
                        min_quantity=min_qty,
                        location=request.POST.get('location'),
                        arrival_date=arrival_date
                    )
            except Exception:
                pass

        return redirect('dashboard')

    # КОНТЕКСТ З ФІЛЬТРАЦІЄЮ ДАНИХ
    context = {
        'is_admin': is_admin,
        'is_manager': is_manager,
        'is_stafflog': is_stafflog,
        'clients': Client.objects.all() if is_manager else [],
        'orders': Order.objects.all().prefetch_related('orderitem_set__product').order_by('-order_date') if is_manager else [],
        'inventory': Inventory.objects.all().select_related('product') if (is_stafflog or is_manager) else [],
        'total_value': Inventory.objects.aggregate(total=Sum(F('product__price') * F('quantity')))['total'] or 0,
        'total_orders_sum': Order.objects.exclude(status="Скасовано").aggregate(total=Sum('total_amount'))['total'] or 0
    }
    return render(request, 'crm_app/dashboard.html', context)


# 5. ЕКСПОРТ ЗВІТУ (Тільки Admin та Stafflog)
@login_required
def export_inventory_report(request):
    user_groups = request.user.groups.values_list('name', flat=True)
    if not (request.user.is_superuser or "Admin" in user_groups or "Stafflog" in user_groups):
        return HttpResponse("У вас немає прав на вигрузку звітів", status=403)

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Звіт_Склад"
    headers = ['Товар', 'Залишок', 'Мін. запас', 'Локація', 'Всього продано', 'Статус']
    ws.append(headers)

    queryset = Inventory.objects.select_related('product').all()
    if start_date and end_date:
        queryset = queryset.filter(arrival_date__range=[start_date, end_date])

    for item in queryset:
        sold_qty = OrderItem.objects.filter(
            product=item.product
        ).exclude(order__status="Скасовано").aggregate(total=Sum('quantity'))['total'] or 0

        status = "Норма"
        if item.quantity <= item.min_quantity: status = "МАЛО"
        if item.quantity <= 0: status = "НЕМАЄ"

        ws.append([item.product.name, item.quantity, item.min_quantity, item.location, sold_qty, status])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="inventory_{datetime.now().strftime("%d_%m")}.xlsx"'
    wb.save(response)
    return response
