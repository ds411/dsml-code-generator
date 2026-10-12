import { NextResponse, type NextRequest } from "next/server";
import { runWithAmplifyServerContext } from "@/shared/amplify";
import { fetchAuthSession } from "aws-amplify/auth/server";

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const response = NextResponse.next();
  const signedIn = await runWithAmplifyServerContext({
    nextServerContext: { request, response },
    operation: async (contextSpec) => {
      const session = await fetchAuthSession(contextSpec);
      return session.tokens !== undefined;
    },
  });
  return signedIn ? response : NextResponse.redirect(new URL("/", request.url));
}

export const config = { matcher: ["/orders/:path*"] };
