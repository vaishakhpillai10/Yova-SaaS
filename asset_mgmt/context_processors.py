from .roles import navigation_for_user, user_role, user_role_label


def role_context(request):
    current_url_name = request.resolver_match.url_name if request.resolver_match else ''
    return {
        'current_role': user_role(request.user),
        'current_role_label': user_role_label(request.user),
        'navigation_sections': navigation_for_user(request.user, current_url_name),
    }
