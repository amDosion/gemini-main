
import { googleMediaStrategy } from "../providers/google/media";

export const MediaFactory = {
    getStrategy: (providerId: string) => {
        switch (providerId) {
            case 'google':
            case 'google-custom':
                return googleMediaStrategy;
            default:
                return googleMediaStrategy; 
        }
    }
};
