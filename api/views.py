"""
API views для Soulpull.
"""
import json
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.db import transaction
from django.utils import timezone

from .models import UserProfile, AuthorCode, Participation, PayoutRequest
from .decorators import admin_token_required


@csrf_exempt
@require_http_methods(["GET"])
def health(request):
    """
    GET /api/v1/health
    Health check endpoint для проверки работоспособности сервера.
    """
    from django.db import connection
    from django.conf import settings
    
    try:
        # Проверка подключения к БД
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Проверка настроек
        checks = {
            'status': 'ok',
            'database': 'connected',
            'django_version': 'ok',
            'settings': {
                'debug': settings.DEBUG,
                'has_admin_token': bool(settings.X_ADMIN_TOKEN),
                'has_receiver_wallet': bool(settings.RECEIVER_WALLET),
            }
        }
        
        return JsonResponse(checks, status=200)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    """
    POST /api/v1/register
    Регистрация нового пользователя по Telegram ID и коду автора.
    
    Body: {
        "telegram_id": int,
        "author_code": str
    }
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        author_code = data.get('author_code')

        if not telegram_id or not author_code:
            return JsonResponse(
                {'error': 'telegram_id and author_code are required'},
                status=400
            )

        # Проверка кода автора
        try:
            code_obj = AuthorCode.objects.get(code=author_code, is_active=True)
            # Проверка срока действия (если указан)
            if code_obj.expires_at and code_obj.expires_at < timezone.now():
                return JsonResponse(
                    {'error': 'Author code has expired'},
                    status=400
                )
        except AuthorCode.DoesNotExist:
            return JsonResponse(
                {'error': 'Invalid or inactive author code'},
                status=400
            )

        # Создание или получение пользователя
        user, created = UserProfile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={}
        )

        return JsonResponse({
            'success': True,
            'user_id': user.id,
            'telegram_id': user.telegram_id,
            'created': created
        }, status=201 if created else 200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def wallet(request):
    """
    POST /api/v1/wallet
    Привязка кошелька к пользователю.
    
    Body: {
        "telegram_id": int,
        "wallet_address": str
    }
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        wallet_address = data.get('wallet_address')

        if not telegram_id or not wallet_address:
            return JsonResponse(
                {'error': 'telegram_id and wallet_address are required'},
                status=400
            )

        try:
            user = UserProfile.objects.get(telegram_id=telegram_id)
            user.wallet_address = wallet_address
            user.save()

            return JsonResponse({
                'success': True,
                'telegram_id': user.telegram_id,
                'wallet_address': user.wallet_address
            })

        except UserProfile.DoesNotExist:
            return JsonResponse(
                {'error': 'User not found'},
                status=404
            )

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def intent(request):
    """
    POST /api/v1/intent
    Создание намерения участия (intent).
    
    Body: {
        "telegram_id": int,
        "amount": str or decimal
    }
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        amount = data.get('amount')

        if not telegram_id or amount is None:
            return JsonResponse(
                {'error': 'telegram_id and amount are required'},
                status=400
            )

        try:
            user = UserProfile.objects.get(telegram_id=telegram_id)
            
            # Преобразование amount в Decimal
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    return JsonResponse(
                        {'error': 'Amount must be positive'},
                        status=400
                    )
            except (InvalidOperation, ValueError):
                return JsonResponse(
                    {'error': 'Invalid amount format'},
                    status=400
                )

            # Здесь можно создать запись о намерении, если нужна отдельная модель
            # Пока просто возвращаем успех
            return JsonResponse({
                'success': True,
                'telegram_id': user.telegram_id,
                'amount': str(amount_decimal)
            })

        except UserProfile.DoesNotExist:
            return JsonResponse(
                {'error': 'User not found'},
                status=404
            )

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def me(request):
    """
    GET /api/v1/me?telegram_id=<id>
    Получение информации о пользователе.
    """
    telegram_id = request.GET.get('telegram_id')

    if not telegram_id:
        return JsonResponse(
            {'error': 'telegram_id parameter is required'},
            status=400
        )

    try:
        telegram_id = int(telegram_id)
    except ValueError:
        return JsonResponse(
            {'error': 'Invalid telegram_id format'},
            status=400
        )

    try:
        user = UserProfile.objects.get(telegram_id=telegram_id)
        
        # Подсчет статистики
        participations = Participation.objects.filter(user=user)
        total_participations = participations.count()
        confirmed_participations = participations.filter(status='CONFIRMED').count()
        
        payout_requests = PayoutRequest.objects.filter(user=user)
        total_payouts = payout_requests.count()
        pending_payouts = payout_requests.filter(status='PENDING').count()

        return JsonResponse({
            'telegram_id': user.telegram_id,
            'wallet_address': user.wallet_address or '',
            'created_at': user.created_at.isoformat(),
            'statistics': {
                'total_participations': total_participations,
                'confirmed_participations': confirmed_participations,
                'total_payouts': total_payouts,
                'pending_payouts': pending_payouts,
            }
        })

    except UserProfile.DoesNotExist:
        return JsonResponse(
            {'error': 'User not found'},
            status=404
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def payout(request):
    """
    POST /api/v1/payout
    Создание запроса на выплату.
    
    Body: {
        "telegram_id": int,
        "amount": str or decimal,
        "wallet_address": str
    }
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        amount = data.get('amount')
        wallet_address = data.get('wallet_address')

        if not telegram_id or amount is None or not wallet_address:
            return JsonResponse(
                {'error': 'telegram_id, amount, and wallet_address are required'},
                status=400
            )

        try:
            user = UserProfile.objects.get(telegram_id=telegram_id)
            
            # Преобразование amount в Decimal
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    return JsonResponse(
                        {'error': 'Amount must be positive'},
                        status=400
                    )
            except (InvalidOperation, ValueError):
                return JsonResponse(
                    {'error': 'Invalid amount format'},
                    status=400
                )

            # Создание запроса на выплату
            payout_request = PayoutRequest.objects.create(
                user=user,
                amount=amount_decimal,
                wallet_address=wallet_address,
                status='PENDING'
            )

            return JsonResponse({
                'success': True,
                'payout_request_id': payout_request.id,
                'amount': str(payout_request.amount),
                'status': payout_request.status
            }, status=201)

        except UserProfile.DoesNotExist:
            return JsonResponse(
                {'error': 'User not found'},
                status=404
            )

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@admin_token_required
@require_http_methods(["POST"])
def payout_mark(request):
    """
    POST /api/v1/payout/mark
    Админский endpoint для изменения статуса выплаты.
    Требует заголовок X-Admin-Token.
    
    Body: {
        "payout_request_id": int,
        "status": "APPROVED" | "REJECTED" | "PAID",
        "admin_notes": str (optional)
    }
    """
    try:
        data = json.loads(request.body)
        payout_request_id = data.get('payout_request_id')
        status = data.get('status')
        admin_notes = data.get('admin_notes', '')

        if not payout_request_id or not status:
            return JsonResponse(
                {'error': 'payout_request_id and status are required'},
                status=400
            )

        valid_statuses = ['APPROVED', 'REJECTED', 'PAID']
        if status not in valid_statuses:
            return JsonResponse(
                {'error': f'Status must be one of: {", ".join(valid_statuses)}'},
                status=400
            )

        try:
            payout_request = PayoutRequest.objects.get(id=payout_request_id)
            payout_request.status = status
            if admin_notes:
                payout_request.admin_notes = admin_notes
            if status in ['APPROVED', 'REJECTED', 'PAID']:
                payout_request.processed_at = timezone.now()
            payout_request.save()

            return JsonResponse({
                'success': True,
                'payout_request_id': payout_request.id,
                'status': payout_request.status,
                'processed_at': payout_request.processed_at.isoformat() if payout_request.processed_at else None
            })

        except PayoutRequest.DoesNotExist:
            return JsonResponse(
                {'error': 'Payout request not found'},
                status=404
            )

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm(request):
    """
    POST /api/v1/confirm
    Подтверждение транзакции по tx_hash.
    Пока не ходит в Toncenter, просто сохраняет tx_hash и переводит статус в CONFIRMED.
    
    Body: {
        "telegram_id": int,
        "tx_hash": str,
        "amount": str or decimal (optional)
    }
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        tx_hash = data.get('tx_hash')
        amount = data.get('amount')

        if not telegram_id or not tx_hash:
            return JsonResponse(
                {'error': 'telegram_id and tx_hash are required'},
                status=400
            )

        try:
            user = UserProfile.objects.get(telegram_id=telegram_id)
            
            # Проверка на дубликат tx_hash
            if Participation.objects.filter(tx_hash=tx_hash).exists():
                return JsonResponse(
                    {'error': 'Transaction hash already exists'},
                    status=400
                )

            # Преобразование amount в Decimal (если указан)
            amount_decimal = None
            if amount is not None:
                try:
                    amount_decimal = Decimal(str(amount))
                    if amount_decimal <= 0:
                        return JsonResponse(
                            {'error': 'Amount must be positive'},
                            status=400
                        )
                except (InvalidOperation, ValueError):
                    return JsonResponse(
                        {'error': 'Invalid amount format'},
                        status=400
                    )

            # Создание записи о participation
            participation = Participation.objects.create(
                user=user,
                tx_hash=tx_hash,
                amount=amount_decimal or Decimal('0'),
                status='CONFIRMED',
                confirmed_at=timezone.now()
            )

            return JsonResponse({
                'success': True,
                'participation_id': participation.id,
                'tx_hash': participation.tx_hash,
                'status': participation.status,
                'confirmed_at': participation.confirmed_at.isoformat()
            }, status=201)

        except UserProfile.DoesNotExist:
            return JsonResponse(
                {'error': 'User not found'},
                status=404
            )

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def jetton_wallet(request):
    """
    GET /api/v1/jetton/wallet?telegram_id=<id>
    Получение адреса jetton кошелька пользователя.
    Пока возвращает заглушку без вызова Toncenter.
    """
    telegram_id = request.GET.get('telegram_id')

    if not telegram_id:
        return JsonResponse(
            {'error': 'telegram_id parameter is required'},
            status=400
        )

    try:
        telegram_id = int(telegram_id)
    except ValueError:
        return JsonResponse(
            {'error': 'Invalid telegram_id format'},
            status=400
        )

    try:
        user = UserProfile.objects.get(telegram_id=telegram_id)
        
        # Заглушка: возвращаем stub вместо реального вызова Toncenter
        return JsonResponse({
            'telegram_id': user.telegram_id,
            'wallet_address': 'stub'
        })

    except UserProfile.DoesNotExist:
        return JsonResponse(
            {'error': 'User not found'},
            status=404
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
